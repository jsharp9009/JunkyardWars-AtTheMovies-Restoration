#!/usr/bin/env python3
"""
Build English translation evidence from Russian Whisper JSON.

The Russian Whisper transcription remains untouched. For each segment this
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
translation decision. Later we can compare these candidates with the
surviving English audio transcription and lip-reading transcription.
"""

import argparse
import gc
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


def normalize_translation(text):
    """Conservative cleanup; do not rewrite model meaning automatically."""
    return re.sub(r"\s+", " ", str(text)).strip()


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


def unload_model(tokenizer, model):
    del tokenizer
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


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


def translate_with_context(index, segments, tokenizer, model, device, radius):
    """Translate one segment while supplying nearby Russian dialogue."""
    group_start = max(0, index - radius)
    group_end = min(len(segments), index + radius + 1)
    group_indices = list(range(group_start, group_end))
    texts = [str(segments[i].get("text", "")).strip() for i in group_indices]

    if not all(texts):
        direct = translate_batch(
            [str(segments[index].get("text", "")).strip()], tokenizer, model, device
        )
        return direct[0].strip() if direct else ""

    translated = translate_context_group(texts, tokenizer, model, device)
    if translated is None:
        direct = translate_batch(
            [str(segments[index].get("text", "")).strip()], tokenizer, model, device
        )
        return direct[0].strip() if direct else ""

    return translated[group_indices.index(index)]


def ensure_candidate_object(segment):
    candidates = segment.get("translation_candidates")
    if not isinstance(candidates, dict):
        candidates = {}
        segment["translation_candidates"] = candidates
    return candidates


def candidate_ready(segment, name):
    candidates = segment.get("translation_candidates", {})
    return isinstance(candidates, dict) and bool(str(candidates.get(name, "")).strip())


def pending_indices(segments, start, stop, candidate_name, force):
    result = []
    for i in range(start, stop):
        text = str(segments[i].get("text", "")).strip()
        if not text:
            continue
        if force or not candidate_ready(segments[i], candidate_name):
            result.append(i)
    return result


def translate_primary(data, start, stop, args, glossary):
    segments = data["segments"]
    pending = pending_indices(
        segments, start, stop, "nllb_context", args.force
    )
    print(f"Primary candidates needed: {len(pending)}")
    if not pending:
        return

    tokenizer, model, device = load_model(args.model, args.device)
    translated_since_save = 0

    for position, index in enumerate(pending, start=1):
        segment = segments[index]
        source_text = str(segment.get("text", "")).strip()
        candidates = ensure_candidate_object(segment)
        segment["translation_glossary_hits"] = glossary_hits(source_text, glossary)

        candidates["nllb_context"] = normalize_translation(
            translate_with_context(
                index,
                segments,
                tokenizer,
                model,
                device,
                max(0, args.context_window),
            )
        )

        direct = translate_batch([source_text], tokenizer, model, device)
        candidates["nllb_direct"] = normalize_translation(
            direct[0] if direct else ""
        )

        # Preserve compatibility with the earlier script. This is merely the
        # primary candidate, not a human-reviewed final translation.
        segment["translation"] = candidates["nllb_context"]
        segment["translation_review"] = segment.get(
            "translation_review",
            {"status": "unreviewed", "selected": "", "confidence": "", "notes": ""},
        )

        translated_since_save += 1
        print(f"Primary: {position}/{len(pending)} (segment {index})")

        if translated_since_save >= args.save_every:
            atomic_save_json(data, Path(args.output))
            print(f"Progress saved: {args.output}")
            translated_since_save = 0

    atomic_save_json(data, Path(args.output))
    unload_model(tokenizer, model)


def translate_secondary(data, start, stop, args):
    if args.secondary_model.lower() == "none":
        print("Secondary model disabled.")
        return

    segments = data["segments"]
    pending = pending_indices(
        segments, start, stop, "secondary_context", args.force
    )
    print(f"Secondary candidates needed: {len(pending)}")
    if not pending:
        return

    # The secondary model is loaded only after the primary model is unloaded.
    # This avoids holding both NLLB models in GPU memory at the same time.
    tokenizer, model, device = load_model(args.secondary_model, args.device)
    translated_since_save = 0

    for position, index in enumerate(pending, start=1):
        segment = segments[index]
        source_text = str(segment.get("text", "")).strip()
        candidates = ensure_candidate_object(segment)

        candidates["secondary_context"] = normalize_translation(
            translate_with_context(
                index,
                segments,
                tokenizer,
                model,
                device,
                max(0, args.context_window),
            )
        )

        direct = translate_batch([source_text], tokenizer, model, device)
        candidates["secondary_direct"] = normalize_translation(
            direct[0] if direct else ""
        )

        translated_since_save += 1
        print(f"Secondary: {position}/{len(pending)} (segment {index})")

        if translated_since_save >= args.save_every:
            atomic_save_json(data, Path(args.output))
            print(f"Progress saved: {args.output}")
            translated_since_save = 0

    atomic_save_json(data, Path(args.output))
    unload_model(tokenizer, model)


def main():
    parser = argparse.ArgumentParser(
        description="Build contextual Russian-to-English translation evidence from Whisper JSON."
    )
    parser.add_argument("--input", required=True, help="Russian Whisper JSON input file.")
    parser.add_argument("--output", required=True, help="Translation evidence JSON output file.")
    parser.add_argument(
        "--srt-output",
        default=None,
        help="English SRT output. Defaults to <output stem>_en.srt.",
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
        help="Number of neighboring Russian segments on each side for context (default: 2).",
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

    # Run models sequentially so the two checkpoints do not simultaneously
    # consume GPU memory. This is especially important for the 1.3B model.
    translate_primary(data, start, stop, args, glossary)
    translate_secondary(data, start, stop, args)

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
    print("The JSON contains multiple translation candidates for later evidence review.")


if __name__ == "__main__":
    main()
