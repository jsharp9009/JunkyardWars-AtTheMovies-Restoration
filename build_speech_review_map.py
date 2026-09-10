"""
Build natural speech-review regions from a restored English track and an English SRT.

The SRT is used as a guide for where dialogue is expected, not as the source of
hard audio cut points. Audio boundaries are selected from nearby quiet regions so
continuous speech is not split simply because an SRT cue starts or ends.

This is intentionally a candidate-generator. The resulting JSON is meant to be
reviewed and adjusted before it becomes the authoritative speech-restoration map.

Example:
    python build_speech_review_map.py \
        --audio final_restored_audio.wav \
        --srt translated_english.srt \
        --output speech_review_map.json

Dependencies:
    numpy
    soundfile

The script does not modify the audio.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


@dataclass
class Cue:
    index: int
    start: float
    end: float
    text: str


@dataclass
class QuietRegion:
    start: float
    end: float


@dataclass
class ReviewRegion:
    id: int
    start: float
    end: float
    subtitle_ids: list[int]
    text: str
    boundary_start_source: str
    boundary_end_source: str
    quality: str = ""
    speaker: str = ""
    speaker_confidence: str = ""
    notes: str = ""


TIME_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)


def parse_timestamp(value: str) -> float:
    match = re.match(r"^(\d+):(\d{2}):(\d{2}),(\d{3})$", value.strip())
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {value!r}")
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def parse_srt(path: Path) -> list[Cue]:
    text = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n"))

    cues: list[Cue] = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if len(lines) < 2:
            continue

        time_line_index = 1 if lines[0].isdigit() else 0
        if time_line_index >= len(lines):
            continue

        match = TIME_RE.match(lines[time_line_index])
        if not match:
            continue

        start = parse_timestamp(lines[time_line_index].split(" --> ")[0])
        end = parse_timestamp(lines[time_line_index].split(" --> ")[1])
        cue_text = " ".join(lines[time_line_index + 1 :]).strip()

        if end <= start or not cue_text:
            continue

        cues.append(Cue(len(cues), start, end, cue_text))

    return cues


def rms_db(audio: np.ndarray, sample_rate: int, window_ms: float) -> tuple[np.ndarray, float]:
    window = max(1, int(sample_rate * window_ms / 1000.0))
    count = len(audio) // window
    if count == 0:
        return np.empty(0, dtype=np.float64), window / sample_rate

    trimmed = audio[: count * window]
    frames = trimmed.reshape(count, window)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1) + 1e-12)
    db = 20.0 * np.log10(np.maximum(rms, 1e-12))
    return db, window / sample_rate


def find_quiet_regions(
    audio: np.ndarray,
    sample_rate: int,
    threshold_db: float,
    min_quiet_seconds: float,
    window_ms: float,
) -> list[QuietRegion]:
    db, step = rms_db(audio, sample_rate, window_ms)
    if len(db) == 0:
        return []

    quiet = db <= threshold_db
    regions: list[QuietRegion] = []
    start_index: int | None = None

    for i, is_quiet in enumerate(quiet):
        if is_quiet and start_index is None:
            start_index = i
        elif not is_quiet and start_index is not None:
            start = start_index * step
            end = i * step
            if end - start >= min_quiet_seconds:
                regions.append(QuietRegion(start, end))
            start_index = None

    if start_index is not None:
        start = start_index * step
        end = len(db) * step
        if end - start >= min_quiet_seconds:
            regions.append(QuietRegion(start, end))

    return regions


def merge_cues(cues: list[Cue], max_gap: float) -> list[list[Cue]]:
    groups: list[list[Cue]] = []
    current: list[Cue] = []

    for cue in cues:
        if not current:
            current = [cue]
            continue

        gap = cue.start - current[-1].end
        if gap <= max_gap:
            current.append(cue)
        else:
            groups.append(current)
            current = [cue]

    if current:
        groups.append(current)

    return groups


def nearest_quiet_boundary(
    target: float,
    quiet_regions: list[QuietRegion],
    search_radius: float,
    direction: str,
) -> tuple[float | None, str]:
    candidates: list[tuple[float, QuietRegion]] = []

    for quiet in quiet_regions:
        if direction == "before":
            boundary = quiet.end
            if boundary <= target and target - boundary <= search_radius:
                candidates.append((target - boundary, quiet))
        else:
            boundary = quiet.start
            if boundary >= target and boundary - target <= search_radius:
                candidates.append((boundary - target, quiet))

    if not candidates:
        return None, "unmatched"

    _, best = min(candidates, key=lambda item: item[0])
    return (best.end if direction == "before" else best.start), "quiet"


def build_regions(
    cues: list[Cue],
    quiet_regions: list[QuietRegion],
    duration: float,
    cue_merge_gap: float,
    boundary_search: float,
    edge_padding: float,
) -> list[ReviewRegion]:
    groups = merge_cues(cues, cue_merge_gap)
    results: list[ReviewRegion] = []

    for group in groups:
        target_start = max(0.0, group[0].start - edge_padding)
        target_end = min(duration, group[-1].end + edge_padding)

        start, start_source = nearest_quiet_boundary(
            target_start,
            quiet_regions,
            boundary_search,
            "before",
        )
        end, end_source = nearest_quiet_boundary(
            target_end,
            quiet_regions,
            boundary_search,
            "after",
        )

        if start is None:
            start = group[0].start
            start_source = "subtitle"
        if end is None:
            end = group[-1].end
            end_source = "subtitle"

        start = max(0.0, start)
        end = min(duration, end)

        # A pathological quiet-boundary match should never invert a region.
        if end <= start:
            start = group[0].start
            end = group[-1].end
            start_source = "subtitle"
            end_source = "subtitle"

        results.append(
            ReviewRegion(
                id=len(results),
                start=round(start, 6),
                end=round(end, 6),
                subtitle_ids=[cue.index for cue in group],
                text=" ".join(cue.text for cue in group),
                boundary_start_source=start_source,
                boundary_end_source=end_source,
            )
        )

    return results


def load_mono_audio(path: Path) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(path, always_2d=False)
    audio = np.asarray(audio)
    if audio.ndim == 2:
        audio = np.mean(audio.astype(np.float64), axis=1)
    else:
        audio = audio.astype(np.float64)
    return audio, int(sample_rate)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build natural speech-review regions from restored audio and an English SRT."
    )
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--srt", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("speech_review_map.json"))
    parser.add_argument(
        "--threshold-db",
        type=float,
        default=-32.0,
        help="Absolute RMS threshold for a quiet window (default: -32 dBFS).",
    )
    parser.add_argument(
        "--min-quiet",
        type=float,
        default=0.20,
        help="Minimum continuous quiet duration in seconds (default: 0.20).",
    )
    parser.add_argument(
        "--window-ms",
        type=float,
        default=20.0,
        help="RMS analysis window in milliseconds (default: 20).",
    )
    parser.add_argument(
        "--cue-merge-gap",
        type=float,
        default=0.80,
        help="Merge nearby SRT cues into one speech region when their gap is <= this value.",
    )
    parser.add_argument(
        "--boundary-search",
        type=float,
        default=2.50,
        help="Search this many seconds around each subtitle boundary for a quiet region.",
    )
    parser.add_argument(
        "--edge-padding",
        type=float,
        default=0.15,
        help="Look slightly outside the SRT cue/group when searching for natural boundaries.",
    )
    args = parser.parse_args()

    if not args.audio.exists():
        raise SystemExit(f"Audio file not found: {args.audio}")
    if not args.srt.exists():
        raise SystemExit(f"SRT file not found: {args.srt}")

    audio, sample_rate = load_mono_audio(args.audio)
    duration = len(audio) / sample_rate
    cues = parse_srt(args.srt)

    if not cues:
        raise SystemExit("No usable SRT cues were found.")

    quiet_regions = find_quiet_regions(
        audio,
        sample_rate,
        args.threshold_db,
        args.min_quiet,
        args.window_ms,
    )

    regions = build_regions(
        cues,
        quiet_regions,
        duration,
        args.cue_merge_gap,
        args.boundary_search,
        args.edge_padding,
    )

    output = {
        "version": 1,
        "audio": str(args.audio),
        "srt": str(args.srt),
        "sample_rate": sample_rate,
        "duration_seconds": round(duration, 6),
        "parameters": {
            "threshold_db": args.threshold_db,
            "min_quiet_seconds": args.min_quiet,
            "window_ms": args.window_ms,
            "cue_merge_gap": args.cue_merge_gap,
            "boundary_search_seconds": args.boundary_search,
            "edge_padding_seconds": args.edge_padding,
        },
        "subtitle_count": len(cues),
        "quiet_region_count": len(quiet_regions),
        "region_count": len(regions),
        "regions": [asdict(region) for region in regions],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    quiet_start_count = sum(r.boundary_start_source == "quiet" for r in regions)
    quiet_end_count = sum(r.boundary_end_source == "quiet" for r in regions)

    print(f"Audio duration       : {duration:.3f}s")
    print(f"SRT cues             : {len(cues)}")
    print(f"Quiet regions        : {len(quiet_regions)}")
    print(f"Review regions       : {len(regions)}")
    print(f"Natural starts       : {quiet_start_count}/{len(regions)}")
    print(f"Natural ends         : {quiet_end_count}/{len(regions)}")
    print(f"Wrote                : {args.output}")


if __name__ == "__main__":
    main()
