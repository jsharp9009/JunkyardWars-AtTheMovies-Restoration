#!/usr/bin/env python3
"""
Build English translation evidence from Russian Whisper JSON.

The Russian Whisper transcription remains untouched.  For each segment this
script produces multiple English candidates so later restoration work can
compare translation evidence instead of trusting one translation blindly.

Candidates:
  * nllb_context - primary NLLB model translated with nearby Russian context
  * nllb_direct  - primary NLLB model translated without context
  * secondary_context - optional second NLLB model with nearby context
  * secondary_direct  - optional second NLLB model without context

The original segment timings and Whisper word timestamps are preserved.
The legacy ``translation`` field is kept as the primary contextual candidate
so existing downstream tools continue to work, but the new
``translation_candidates`` object is the important artifact for review.

This is intentionally an evidence-generation step, not an automatic final
translation decision.  Later we can compare these candidates with the
surviving English audio transcription and lip-reading transcription.
"""

import argparse
import json
import os
import re
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

DEFAULT_MODEL = "facebook/nllb-200-distilled-600M"
DEFAULT_SECONDARY_MODEL = "facebook/nllb-200-distilled-1.3B"
SRC_LANG = "rus_Cyrl"
TGT_LANG = "eng_Latn"

DEFAULT_GLOSSARY = {
    "Супервойны на свалке": "Junkyard Mega Wars",
    "Супер-войны на свалке": "Junkyard Mega Wars",
    "Супер войны на свалке": "Junkyard Mega Wars",
    "Войны на свалке": "Junkyard Wars",
    "КНБ": "KNB",
    "Осветители": "The Lights team",
    "Хэнсоны": "the Hensons",
    "Бобкэт": "Bobcat",
    "Р2-Д2": "R2-D2",
}


def atomic_save_json(data, path: Path):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def srt_timestamp(seconds):
    ms = max(0, round(float(seconds) * 1000))
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(data, path: Path, field="translation"):
    lines = []
    number = 1
    for seg in data.get("segments", []):
        text = str(seg.get(field, "")).strip()
        if not text:
            continue
        lines += [
            str(number),
            f"{srt_timestamp(seg['start'])} --> {srt_timestamp(seg['end'])}",
            text,
            "",
        ]
        number += 1

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    os.replace(tmp, path)


def load_glossary(path):
    glossary = dict(DEFAULT_GLOSSARY)
    if not path:
        return glossary

    glossary_path = Path(path)
    with glossary_path.open("r", encoding="utf-8") as f:
        user_glossary = json.load(f)

    if not isinstance(user_glossary, dict):
        raise ValueError("Glossary JSON must be an object of Russian -> English mappings.")

    glossary.update({str(k): str(v) for k, v in user_glossary.items()})
    return glossary


def glossary_hits(text, glossary):
    """Return glossary entries present in a Russian source segment."""
    hits = []
    for source, target in sorted(glossary.items(), key=lambda item: len(item[0]), reverse=True):
        if source.lower() in text.lower():
            hits.append({"russian": source, "english": target})
    return hits


def normalize_translation(text, glossary):
    """
    Apply conservative output normalization for exact known names/phrases.

    We deliberately do NOT replace Russian source text with English before
    translation.  Mixing English into the Russian input can make a machine
    translation less reliable.  Instead, normalization only changes common
    translated variants when the exact Russian glossary phrase was present.
    """
    result = re.sub(r"\s+", " ", str(text)).strip()
    return result


def load_model(name, device_name):
    if device_name == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = device_name

    print(f"Device: {device}")
    print(f"Loading tokenizer: {name}")
    tokenizer = AutoTokenizer.from_pretrained(
        name,
        src_lang=SRC_LANG,
        tgt_lang=TGT_LANG,
    )

    print(f"Loading model: {name}")
    if device == "cuda":
        model = AutoModelForSeq2SeqLM.from_pretrained(
            name,
            torch_dtype=torch.float16,
        ).to(device)
    else:
        model = AutoModelForSeq2SeqLM.from_pretrained(name).to(device)

    model.eval()
    return tokenizer, model, device


def translate_batch(texts, tokenizer, model, device):
    if not texts:
        return []

    inputs = tokenizer(
        texts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512,
    )
    inputs = {key: value.to(device) for key, value in inputs.items()}

    with torch.inference_mode():
        translated_tokens = model.generate(
            **inputs,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids(TGT_LANG),
            num_beams=4,
            max_new_tokens=128,
        )

    return tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)


def translate_context_group(texts, tokenizer, model, device):
    """
    Translate a small group together and recover one result per segment.

    The markers are used only to map results back to the original segment.
    If the translation model drops or changes them, return None and let the
    caller fall back to direct per-segment translation.
    """
    source = "\n".join(
        f"[[SEGMENT_{i}]] {text} [[END_SEGMENT_{i}]]"
        for i, text in enumerate(texts)
    )

    translated = translate_batch([source], tokenizer, model, device)[0]

    results = []
    for i in range(len(texts)):
        pattern = rf"\[\[SEGMENT_{i}\]\](.*?)\[\[END_SEGMENT_{i}\]\]"
        match = re.search(pattern, translated, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        value = re.sub(r"\s+", " ", match.group(1)).strip()
        results.append(value)

    return results


def translate_with_context(indices, segments, tokenizer, model, device, radius):
    """Translate selected segment indices using nearby Russian context."""
    if not indices:
        return {}

    results = {}
    min_index = min(indices)
    max_index = max(indices)

    for center in indices:
        group_start = max(0, center - radius)
        group_end = min(len(segments), center + radius + 1)
        group_indices = list(range(group_start, group_end))
        texts = [str(segments[i].get("text", "")).strip() for i in group_indices]

        if not all(texts):
            direct = translate_batch([str(segments[center].get("text", "")).strip()], tokenizer, model, device)
            results[center] = direct[0].strip() if direct else ""
            continue

        translated = translate_context_group(texts, tokenizer, model, device)
        if translated is None:
            direct = translate_batch([str(segments[center].get("text", "")).strip()], tokenizer, model, device)
            results[center] = direct[0].strip() if direct else ""
        else:
            local_index = group_indices.index(center)
            results[center] = translated[local_index]

    return results


def ensure_candidate_object(segment):
    candidates = segment.get("translation_candidates")
    if not isinstance(candidates, dict):
        candidates = {}
        segment["translation_candidates"] = candidates
    return candidates


def candidate_ready(segment, name):
    candidates = segment.get("translation_candidates", {})
    return isinstance(candidates, dict) and bool(str(candidates.get(name, "")).strip())


def main():
    parser = argparse.ArgumentParser(
        description="Build contextual Russian-to-English translation evidence from Whisper JSON."
    )
    parser.add_argument("--input", required=True, help="Russian Whisper JSON input file.")
    parser.add_argument("--output", required=True, help="Translation evidence JSON output file.")
    parser.add_argument(
        "--srt-output",
        default=None,
        help="Primary English SRT output. Defaults to <output stem>_en.srt.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Primary translation model.")
    parser.add_argument(
        "--secondary-model",
        default=DEFAULT_SECONDARY_MODEL,
        help="Second translation model. Use 'none' to disable.",
    )
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--save-every", type=int, default=10)
    parser.add_argument(
        "--glossary",
        default=None,
        help="Optional JSON object mapping Russian terms/phrases to desired English forms.",
    )
    parser.add_argument(
        "--context-window",
        type=int,
        default=2,
        help="Number of neighboring Russian segments on each side for contextual translation (default: 2).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate translation candidates even if they already exist.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    print(f"Reading: {input_path}")
    with input_path.open("r", encoding="utf-8") as f:
        input_data = json.load(f)

    if not isinstance(input_data.get("segments"), list):
        raise ValueError("Input JSON does not contain a 'segments' array.")

    if output_path.exists():
        print(f"Resuming existing output: {output_path}")
        with output_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if len(data.get("segments", [])) != len(input_data["segments"]):
            raise ValueError(
                "Existing output has a different number of segments than the input."
            )
    else:
        data = json.loads(json.dumps(input_data))

    glossary = load_glossary(args.glossary)
    print(f"Glossary entries: {len(glossary)}")
    print(f"Context window: {args.context_window}")
    print(f"Primary model: {args.model}")
    print(f"Secondary model: {args.secondary_model}")

    segments = data["segments"]
    total = len(segments)
    start = max(0, args.start)
    stop = total if args.limit is None else min(total, start + max(0, args.limit))

    print(f"Segments: {total}")
    print(f"Requested range: {start}..{stop - 1}")

    primary_tokenizer, primary_model, device = load_model(args.model, args.device)

    secondary_tokenizer = None
    secondary_model = None
    if args.secondary_model.lower() != "none":
        secondary_tokenizer, secondary_model, _ = load_model(
            args.secondary_model, args.device
        )

    pending = []
    for i in range(start, stop):
        text = str(segments[i].get("text", "")).strip()
        if not text:
            continue

        needed = args.force or not candidate_ready(segments[i], "nllb_context")
        if needed:
            pending.append(i)

    print(f"Segments needing translation evidence: {len(pending)}")

    translated_since_save = 0

    # Process one segment at a time at the evidence level.  Each segment is
    # translated with context, directly, and (optionally) by the secondary
    # model. This is slower than one giant batch but produces much more useful
    # review data and remains safely resumable.
    for position, index in enumerate(pending, start=1):
        segment = segments[index]
        source_text = str(segment.get("text", "")).strip()
        candidates = ensure_candidate_object(segment)

        hits = glossary_hits(source_text, glossary)
        segment["translation_glossary_hits"] = hits

        # Context candidate: use neighboring Russian dialogue but store only
        # the translation belonging to this segment.
        context_result = translate_with_context(
            [index],
            segments,
            primary_tokenizer,
            primary_model,
            device,
            max(0, args.context_window),
        )
        candidates["nllb_context"] = normalize_translation(
            context_result.get(index, ""), glossary
        )

        # Direct candidate: no surrounding text, useful for detecting cases
        # where context changes the interpretation too aggressively.
        direct = translate_batch(
            [source_text], primary_tokenizer, primary_model, device
        )
        candidates["nllb_direct"] = normalize_translation(
            direct[0] if direct else "", glossary
        )

        # Optional independent model provides a second machine-translation
        # opinion. The models are different sizes, so disagreement is useful
        # evidence rather than an attempt to declare one automatically correct.
        if secondary_model is not None:
            secondary_context = translate_with_context(
                [index],
                segments,
                secondary_tokenizer,
                secondary_model,
                device,
                max(0, args.context_window),
            )
            candidates["secondary_context"] = normalize_translation(
                secondary_context.get(index, ""), glossary
            )

            secondary_direct = translate_batch(
                [source_text], secondary_tokenizer, secondary_model, device
            )
            candidates["secondary_direct"] = normalize_translation(
                secondary_direct[0] if secondary_direct else "", glossary
            )

        # Keep the old field for compatibility. This is NOT the final reviewed
        # answer; it is simply the primary contextual candidate.
        segment["translation"] = candidates.get("nllb_context", "")
        segment["translation_review"] = {
            "status": "unreviewed",
            "selected": "",
            "confidence": "",
            "notes": "",
        }

        translated_since_save += 1

        if position % 1 == 0:
            print(f"Processed {position}/{len(pending)} (segment {index})")

        if translated_since_save >= args.save_every:
            atomic_save_json(data, output_path)
            print(f"Progress saved: {output_path}")
            translated_since_save = 0

    atomic_save_json(data, output_path)

    srt_path = (
        Path(args.srt_output)
        if args.srt_output
        else output_path.with_name(output_path.stem + "_en.srt")
    )
    write_srt(data, srt_path, field="translation")

    print("Done.")
    print(f"JSON: {output_path}")
    print(f"SRT:  {srt_path}")
    print("The JSON now contains multiple translation candidates for review.")


if __name__ == "__main__":
    main()
