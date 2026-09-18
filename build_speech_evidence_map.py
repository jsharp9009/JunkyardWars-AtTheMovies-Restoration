#!/usr/bin/env python3
"""
Build a dialogue evidence map by joining speech-review regions with:

1. Russian Whisper/translation JSON
2. recovered-English Whisper JSON
3. the human speech-review metadata

The output is deliberately an evidence artifact, not a final transcript.

Important:
- Region boundaries come from speech_review_map.json.
- Russian/translation segments are matched primarily by time overlap, not
  subtitle/segment IDs, because the review map and translation JSON may have
  different cue numbering.
- English ASR is treated as evidence only. It is never promoted to final text
  automatically.
- No source text is rewritten or "corrected" by this script.

Example:
    python build_speech_evidence_map.py \
        --review-map speech_review_map.json \
        --translation translation_text.json \
        --english-asr audio_large.json \
        --output speech_evidence_map.json

The output is intended to drive the Speech Review UI. Each region contains:
- the natural audio review region
- Russian source evidence
- all available translation candidates
- recovered-English ASR evidence
- existing human quality/speaker metadata
- conservative evidence flags
- an empty human-review section for final wording and confidence
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


CANDIDATE_FIELDS = (
    "nllb_context",
    "nllb_direct",
    "secondary_context",
    "secondary_direct",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def normalize_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text


def overlap_seconds(
    start_a: float,
    end_a: float,
    start_b: float,
    end_b: float,
) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def overlap_ratio(
    start_a: float,
    end_a: float,
    start_b: float,
    end_b: float,
) -> float:
    duration = max(0.0, end_a - start_a)
    if duration <= 0:
        return 0.0
    return overlap_seconds(start_a, end_a, start_b, end_b) / duration


def segment_matches_region(
    segment: dict[str, Any],
    region_start: float,
    region_end: float,
    min_overlap: float,
) -> bool:
    start = float(segment.get("start", 0.0))
    end = float(segment.get("end", start))
    if end <= start:
        return False

    overlap = overlap_seconds(region_start, region_end, start, end)
    if overlap <= 0:
        return False

    # Keep a segment when a meaningful portion of the segment lies in the
    # review region, or when its midpoint is inside the region. The midpoint
    # rule prevents very short utterances from disappearing at boundaries.
    if overlap / (end - start) >= min_overlap:
        return True

    midpoint = (start + end) / 2.0
    return region_start <= midpoint <= region_end


def select_segments(
    segments: list[dict[str, Any]],
    region_start: float,
    region_end: float,
    min_overlap: float,
) -> list[dict[str, Any]]:
    selected = [
        segment
        for segment in segments
        if segment_matches_region(segment, region_start, region_end, min_overlap)
    ]
    selected.sort(key=lambda item: (float(item.get("start", 0.0)), int(item.get("id", 0))))
    return selected


def candidate_values(segment: dict[str, Any]) -> dict[str, str]:
    candidates = segment.get("translation_candidates", {})
    if not isinstance(candidates, dict):
        candidates = {}

    values: dict[str, str] = {}
    for field in CANDIDATE_FIELDS:
        value = normalize_text(candidates.get(field, ""))
        if value:
            values[field] = value
    return values


def normalized_for_compare(value: str) -> str:
    value = normalize_text(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def candidate_disagreement(segments: list[dict[str, Any]]) -> bool:
    values: set[str] = set()

    for segment in segments:
        for value in candidate_values(segment).values():
            normalized = normalized_for_compare(value)
            if normalized:
                values.add(normalized)

    return len(values) > 1


def collect_russian_evidence(
    segments: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    source_segments: list[dict[str, Any]] = []
    russian_text_parts: list[str] = []

    for segment in segments:
        text = normalize_text(segment.get("text", ""))
        if not text:
            continue

        source = {
            "id": segment.get("id"),
            "start": float(segment.get("start", 0.0)),
            "end": float(segment.get("end", 0.0)),
            "russian_text": text,
            "translation_candidates": candidate_values(segment),
            "translation": normalize_text(segment.get("translation", "")),
            "glossary_hits": segment.get("translation_glossary_hits", []),
            "glossary_corrections": segment.get("translation_glossary_corrections", []),
            "translation_review": segment.get(
                "translation_review",
                {
                    "status": "unreviewed",
                    "selected": "",
                    "confidence": "",
                    "notes": "",
                },
            ),
        }
        source_segments.append(source)
        russian_text_parts.append(text)

    return " ".join(russian_text_parts), source_segments


def word_confidence(segment: dict[str, Any]) -> float | None:
    words = segment.get("words")
    if not isinstance(words, list):
        return None

    probabilities: list[float] = []
    for word in words:
        if not isinstance(word, dict):
            continue
        probability = word.get("probability")
        if isinstance(probability, (int, float)) and math.isfinite(float(probability)):
            probabilities.append(float(probability))

    if not probabilities:
        return None

    return sum(probabilities) / len(probabilities)


def collect_english_asr(
    segments: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], float | None]:
    text_parts: list[str] = []
    evidence_segments: list[dict[str, Any]] = []
    confidences: list[float] = []

    for segment in segments:
        text = normalize_text(segment.get("text", ""))
        if text:
            text_parts.append(text)

        confidence = word_confidence(segment)
        if confidence is not None:
            confidences.append(confidence)

        evidence_segments.append(
            {
                "id": segment.get("id"),
                "start": float(segment.get("start", 0.0)),
                "end": float(segment.get("end", 0.0)),
                "text": text,
                "word_confidence": (
                    round(confidence, 4) if confidence is not None else None
                ),
                "no_speech_probability": segment.get("no_speech_prob"),
                "avg_logprob": segment.get("avg_logprob"),
            }
        )

    average_confidence = (
        sum(confidences) / len(confidences) if confidences else None
    )
    return (
        " ".join(text_parts),
        evidence_segments,
        average_confidence,
    )


def build_flags(
    region: dict[str, Any],
    translation_segments: list[dict[str, Any]],
    english_segments: list[dict[str, Any]],
    english_confidence: float | None,
) -> dict[str, Any]:
    quality = normalize_text(region.get("quality", ""))
    speaker = normalize_text(region.get("speaker", ""))

    flags: list[str] = []

    if quality in {"Muffled", "Partial", "Missing"}:
        flags.append(f"quality_{quality.lower()}")

    if speaker == "Multiple":
        flags.append("multiple_speakers")

    if not translation_segments:
        flags.append("no_russian_translation_evidence")

    if candidate_disagreement(translation_segments):
        flags.append("translation_candidates_disagree")

    if not english_segments:
        flags.append("no_recovered_english_asr")

    if english_segments and english_confidence is not None and english_confidence < 0.45:
        flags.append("low_english_asr_confidence")

    if english_segments:
        asr_text = " ".join(
            normalize_text(segment.get("text", ""))
            for segment in english_segments
        )
        if not asr_text:
            flags.append("empty_english_asr")

    needs_attention = bool(flags)

    return {
        "needs_attention": needs_attention,
        "flags": flags,
    }


def build_region(
    region: dict[str, Any],
    translation_segments: list[dict[str, Any]],
    english_segments: list[dict[str, Any]],
) -> dict[str, Any]:
    start = float(region.get("start", 0.0))
    end = float(region.get("end", start))

    russian_text, translation_evidence = collect_russian_evidence(
        translation_segments
    )
    english_asr_text, english_evidence, english_confidence = collect_english_asr(
        english_segments
    )

    flags = build_flags(
        region,
        translation_segments,
        english_segments,
        english_confidence,
    )

    return {
        "id": region.get("id"),
        "start": start,
        "end": end,
        "duration": round(max(0.0, end - start), 6),
        "subtitle_ids": list(region.get("subtitle_ids", [])),
        "translated_region_text": normalize_text(region.get("text", "")),
        "boundary": {
            "start_source": normalize_text(region.get("boundary_start_source", "")),
            "end_source": normalize_text(region.get("boundary_end_source", "")),
        },
        "review_metadata": {
            "quality": normalize_text(region.get("quality", "")),
            "speaker": normalize_text(region.get("speaker", "")),
            "speaker_confidence": normalize_text(region.get("speaker_confidence", "")),
            "known_speaker_name": normalize_text(region.get("known_speaker_name", "")),
            "notes": normalize_text(region.get("notes", "")),
        },
        "russian_evidence": {
            "text": russian_text,
            "segments": translation_evidence,
        },
        "recovered_english_asr": {
            "text": english_asr_text,
            "segments": english_evidence,
            "average_word_confidence": (
                round(english_confidence, 4)
                if english_confidence is not None
                else None
            ),
        },
        "evidence_flags": flags,
        "review": {
            "status": "unreviewed",
            "final_text": "",
            "confidence": "",
            "evidence": "",
            "notes": "",
        },
    }


def build_map(
    review_map: dict[str, Any],
    translation_data: dict[str, Any],
    english_data: dict[str, Any],
    min_overlap: float,
) -> dict[str, Any]:
    regions = review_map.get("regions", [])
    translation_segments = translation_data.get("segments", [])
    english_segments = english_data.get("segments", [])

    if not isinstance(regions, list):
        raise ValueError("Review map does not contain a 'regions' array.")
    if not isinstance(translation_segments, list):
        raise ValueError("Translation JSON does not contain a 'segments' array.")
    if not isinstance(english_segments, list):
        raise ValueError("English ASR JSON does not contain a 'segments' array.")

    output_regions: list[dict[str, Any]] = []

    for region in regions:
        if not isinstance(region, dict):
            continue

        start = float(region.get("start", 0.0))
        end = float(region.get("end", start))

        matching_translation = select_segments(
            translation_segments,
            start,
            end,
            min_overlap,
        )
        matching_english = select_segments(
            english_segments,
            start,
            end,
            min_overlap,
        )

        output_regions.append(
            build_region(
                region,
                matching_translation,
                matching_english,
            )
        )

    attention_count = sum(
        region["evidence_flags"]["needs_attention"]
        for region in output_regions
    )

    return {
        "version": 1,
        "purpose": (
            "Dialogue evidence map for human review. This artifact combines "
            "Russian transcription/translation evidence with recovered-English "
            "ASR and existing speech-review metadata. It does not determine "
            "final wording automatically."
        ),
        "sources": {
            "speech_review_map": review_map.get("audio", ""),
            "translation_json": "",
            "english_asr_json": "",
        },
        "source_metadata": {
            "review_region_count": len(regions),
            "translation_segment_count": len(translation_segments),
            "english_asr_segment_count": len(english_segments),
            "translation_overlap_threshold": min_overlap,
        },
        "statistics": {
            "regions": len(output_regions),
            "regions_needing_attention": attention_count,
            "regions_without_russian_evidence": sum(
                not region["russian_evidence"]["segments"]
                for region in output_regions
            ),
            "regions_without_english_asr": sum(
                not region["recovered_english_asr"]["segments"]
                for region in output_regions
            ),
            "translation_disagreement_regions": sum(
                "translation_candidates_disagree"
                in region["evidence_flags"]["flags"]
                for region in output_regions
            ),
            "low_english_asr_confidence_regions": sum(
                "low_english_asr_confidence"
                in region["evidence_flags"]["flags"]
                for region in output_regions
            ),
        },
        "regions": output_regions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a dialogue evidence map from speech-review, translation, and English ASR JSON."
    )
    parser.add_argument("--review-map", type=Path, required=True)
    parser.add_argument("--translation", type=Path, required=True)
    parser.add_argument("--english-asr", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("speech_evidence_map.json"),
    )
    parser.add_argument(
        "--min-overlap",
        type=float,
        default=0.20,
        help=(
            "Minimum fraction of a source segment that must overlap a review "
            "region before it is included (default: 0.20)."
        ),
    )
    args = parser.parse_args()

    if not 0.0 <= args.min_overlap <= 1.0:
        raise SystemExit("--min-overlap must be between 0 and 1.")

    for path in (args.review_map, args.translation, args.english_asr):
        if not path.exists():
            raise SystemExit(f"Input file not found: {path}")

    review_map = load_json(args.review_map)
    translation_data = load_json(args.translation)
    english_data = load_json(args.english_asr)

    evidence_map = build_map(
        review_map,
        translation_data,
        english_data,
        args.min_overlap,
    )

    evidence_map["sources"]["translation_json"] = str(args.translation)
    evidence_map["sources"]["english_asr_json"] = str(args.english_asr)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence_map, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Review regions                 : {evidence_map['statistics']['regions']}")
    print(
        "Regions needing attention     : "
        f"{evidence_map['statistics']['regions_needing_attention']}"
    )
    print(
        "Without Russian evidence      : "
        f"{evidence_map['statistics']['regions_without_russian_evidence']}"
    )
    print(
        "Without recovered English ASR : "
        f"{evidence_map['statistics']['regions_without_english_asr']}"
    )
    print(
        "Translation disagreement      : "
        f"{evidence_map['statistics']['translation_disagreement_regions']}"
    )
    print(
        "Low English ASR confidence    : "
        f"{evidence_map['statistics']['low_english_asr_confidence_regions']}"
    )
    print(f"Wrote                         : {args.output}")


if __name__ == "__main__":
    main()
