#!/usr/bin/env python3
"""
Translate Russian Whisper JSON to English with NLLB.

The original Russian JSON and all Whisper word timestamps are preserved.
Each segment gets an English ``translation`` field and an English SRT can
be generated from the original segment timings.

This script has two improvements for this episode:

1. A project glossary can force known Russian terms/proper names to their
   desired English forms.
2. Optional context mode translates small groups of neighboring segments
   together.  This gives NLLB more surrounding dialogue when the current
   segment is ambiguous.  The original per-segment timings are still kept.

NLLB is a general machine-translation model, not a document/context-aware
translation model, so context mode is deliberately conservative. If the
model does not preserve the segment markers, the script falls back to
individual segment translation for that group.
"""

import argparse
import json
import os
import re
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

DEFAULT_MODEL = "facebook/nllb-200-distilled-600M"
SRC_LANG = "rus_Cyrl"
TGT_LANG = "eng_Latn"

# These are deliberately small, high-confidence defaults. More terms can be
# supplied with --glossary without changing the script.
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


def write_srt(data, path: Path):
    lines = []
    number = 1
    for seg in data.get("segments", []):
        text = str(seg.get("translation", "")).strip()
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

    # User entries override defaults.
    glossary.update({str(k): str(v) for k, v in user_glossary.items()})
    return glossary


def apply_glossary_to_source(text, glossary):
    """
    Replace known source phrases with their desired English terminology before
    translation. This is intentionally limited to exact phrases so ordinary
    uses of individual Russian words are not globally rewritten.
    """
    result = text
    # Longest phrases first prevents a short phrase from consuming part of a
    # longer known title/name.
    for source, target in sorted(glossary.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(source, target)
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

    return tokenizer.batch_decode(
        translated_tokens,
        skip_special_tokens=True,
    )


def translate_context_group(texts, tokenizer, model, device):
    """
    Translate a small group of neighboring segments together.

    Markers are included so we can put the translated text back onto the
    correct original segments. If NLLB changes/drops the markers, return None
    and the caller will fall back to individual translation.
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


def main():
    parser = argparse.ArgumentParser(
        description="Translate Russian Whisper JSON to English with NLLB."
    )
    parser.add_argument("--input", required=True, help="Russian Whisper JSON input file.")
    parser.add_argument("--output", required=True, help="Translated JSON output file.")
    parser.add_argument(
        "--srt-output",
        default=None,
        help="English SRT output. Defaults to <output stem>_en.srt.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--save-every", type=int, default=25)
    parser.add_argument(
        "--glossary",
        default=None,
        help="Optional JSON object mapping Russian terms/phrases to desired English forms.",
    )
    parser.add_argument(
        "--context-window",
        type=int,
        default=1,
        help="Neighboring segments on each side for context mode; 0 disables it (default: 1).",
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

    segments = data["segments"]
    total = len(segments)
    start = max(0, args.start)
    stop = total if args.limit is None else min(total, start + max(0, args.limit))

    print(f"Segments: {total}")
    print(f"Requested range: {start}..{stop - 1}")

    tokenizer, model, device = load_model(args.model, args.device)
    translated_since_save = 0

    # Context mode works in small overlapping groups. Each group is translated
    # once and the markers identify which result belongs to which segment.
    # Groups are deliberately small because NLLB is not intended for long
    # document translation.
    if args.context_window > 0:
        i = start
        while i < stop:
            if str(segments[i].get("translation", "")).strip():
                i += 1
                continue

            radius = max(1, args.context_window)
            group_start = max(start, i - radius)
            group_end = min(stop, i + radius + 1)
            group_indices = list(range(group_start, group_end))

            # If every segment in the group is already translated, move on.
            pending_indices = [
                j for j in group_indices
                if not str(segments[j].get("translation", "")).strip()
            ]
            if not pending_indices:
                i += 1
                continue

            source_texts = []
            for j in group_indices:
                raw = str(segments[j].get("text", "")).strip()
                source_texts.append(apply_glossary_to_source(raw, glossary))

            # Context translation is attempted only when all source segments
            # contain text. Empty Whisper segments are handled separately.
            if all(source_texts):
                translated = translate_context_group(
                    source_texts, tokenizer, model, device
                )
            else:
                translated = None

            if translated is None:
                # Safe fallback: translate each pending segment independently.
                fallback_texts = [source_texts[group_indices.index(j)] for j in pending_indices]
                translated = translate_batch(
                    fallback_texts, tokenizer, model, device
                )
                for j, text in zip(pending_indices, translated):
                    segments[j]["translation"] = text.strip()
                    translated_since_save += 1
            else:
                for local_index, j in enumerate(group_indices):
                    if not str(segments[j].get("translation", "")).strip():
                        segments[j]["translation"] = translated[local_index].strip()
                        translated_since_save += 1

            print(f"Processed through segment {i}")

            if translated_since_save >= args.save_every:
                atomic_save_json(data, output_path)
                print(f"Progress saved: {output_path}")
                translated_since_save = 0

            i += 1
    else:
        # Original independent-segment mode.
        for batch_start in range(start, stop, args.batch_size):
            batch_end = min(stop, batch_start + args.batch_size)
            indices = []
            texts = []

            for i in range(batch_start, batch_end):
                if str(segments[i].get("translation", "")).strip():
                    continue
                text = str(segments[i].get("text", "")).strip()
                if text:
                    indices.append(i)
                    texts.append(apply_glossary_to_source(text, glossary))
                else:
                    segments[i]["translation"] = ""

            if indices:
                translations = translate_batch(texts, tokenizer, model, device)
                for index, translation in zip(indices, translations):
                    segments[index]["translation"] = translation.strip()
                    translated_since_save += 1

            print(f"Processed through segment {batch_end - 1}")

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
    write_srt(data, srt_path)

    print("Done.")
    print(f"JSON: {output_path}")
    print(f"SRT:  {srt_path}")


if __name__ == "__main__":
    main()
