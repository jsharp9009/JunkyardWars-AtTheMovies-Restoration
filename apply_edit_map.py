import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa


@dataclass
class Edit:
    start: float
    end: float
    action: str
    note: str
    line_number: int


# Keep transitions short so the edit does not create clicks while preserving
# the character of the combined region.
BOUNDARY_FADE_SECONDS = 0.050


def load_edit_map(csv_path: Path) -> list[Edit]:
    edits = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required_columns = {"start", "end", "action", "note"}

        if reader.fieldnames is None:
            raise ValueError("Edit map CSV does not contain a header.")

        missing = required_columns - set(reader.fieldnames)

        if missing:
            raise ValueError(
                f"Edit map is missing required columns: "
                f"{', '.join(sorted(missing))}"
            )

        for line_number, row in enumerate(reader, start=2):
            try:
                start = float(row["start"])
                end = float(row["end"])
            except ValueError as exc:
                raise ValueError(
                    f"Invalid timestamp on CSV line {line_number}: {exc}"
                )

            if end < start:
                raise ValueError(
                    f"Invalid time range on CSV line {line_number}: "
                    f"{start} -> {end}"
                )

            if end == start:
                print(
                    f"WARNING: CSV line {line_number} has a zero-duration range "
                    f"at {start:.6f}s. Skipping."
                )
                continue

            action = row["action"].strip().lower()
            note = row["note"].strip()

            edits.append(
                Edit(
                    start=start,
                    end=end,
                    action=action,
                    note=note,
                    line_number=line_number,
                )
            )

    edits.sort(key=lambda edit: edit.start)

    return edits


def get_audio_info(path: Path):
    with sf.SoundFile(path) as audio_file:
        return {
            "samplerate": audio_file.samplerate,
            "channels": audio_file.channels,
            "frames": audio_file.frames,
            "duration": audio_file.frames / audio_file.samplerate,
            "subtype": audio_file.subtype,
        }


def seconds_to_sample(time_seconds: float, sample_rate: int) -> int:
    return int(round(time_seconds * sample_rate))


def validate_edits(edits: list[Edit], duration: float):
    previous_end = 0.0

    for edit in edits:
        if edit.start < 0:
            raise ValueError(
                f"CSV line {edit.line_number}: "
                f"start time cannot be negative."
            )

        if edit.end > duration:
            print(
                f"Warning: CSV line {edit.line_number}: end time {edit.end:.6f}s "
                f"exceeds audio duration {duration:.6f}s. "
                f"Clamping to {duration:.6f}s."
            )
            edit.end = duration

        if edit.start < previous_end:
            raise ValueError(
                f"CSV line {edit.line_number}: overlaps with "
                f"a previous edit."
            )

        previous_end = edit.end


def validate_audio(stitched_info, silence_info):
    if stitched_info["channels"] != silence_info["channels"]:
        raise ValueError(
            "Channel counts do not match: "
            f"{stitched_info['channels']} vs "
            f"{silence_info['channels']}"
        )


def print_audio_info(name: str, info: dict):
    print(f"{name}:")
    print(f"  Sample rate: {info['samplerate']}")
    print(f"  Channels:    {info['channels']}")
    print(f"  Frames:      {info['frames']}")
    print(f"  Duration:    {info['duration']:.6f}s")
    print(f"  Subtype:     {info['subtype']}")


def build_equal_power_fades(length: int) -> tuple[np.ndarray, np.ndarray]:
    if length <= 0:
        return np.empty(0, dtype=np.float32), np.empty(0, dtype=np.float32)

    theta = np.linspace(
        0.0,
        np.pi / 2.0,
        length,
        dtype=np.float32,
    )

    return np.cos(theta), np.sin(theta)


def apply_boundary_crossfades(
    output: np.ndarray,
    mixed_region: np.ndarray,
    start_sample: int,
    end_sample: int,
    sample_rate: int,
):
    """Blend a mixed region into the surrounding output without clicks."""
    region_length = end_sample - start_sample

    if region_length <= 0:
        return

    fade_samples = min(
        seconds_to_sample(BOUNDARY_FADE_SECONDS, sample_rate),
        region_length // 2,
    )

    if fade_samples <= 0:
        output[start_sample:end_sample] = mixed_region
        return

    fade_out, fade_in = build_equal_power_fades(fade_samples)

    # Start boundary: original output -> mixed region.
    if start_sample > 0:
        length = min(fade_samples, start_sample)
        previous = output[start_sample - length:start_sample].copy()
        output[start_sample:start_sample + length] = (
            previous * fade_out[-length:, None]
            + mixed_region[:length] * fade_in[-length:, None]
        )
    else:
        length = 0

    # End boundary: mixed region -> original output.
    if end_sample < len(output):
        length = min(fade_samples, len(output) - end_sample)
        following = output[end_sample:end_sample + length].copy()
        output[end_sample - length:end_sample] = (
            mixed_region[-length:] * fade_out[:length, None]
            + following * fade_in[:length, None]
        )

    output[start_sample + length if start_sample > 0 else start_sample:end_sample - (length if end_sample < len(output) else 0)] = mixed_region[
        (fade_samples if start_sample > 0 else 0):
        -(fade_samples if end_sample < len(output) else 0) or None
    ]


def combine_audio(
    stitched_region: np.ndarray,
    silence_region: np.ndarray,
) -> np.ndarray:
    """Mix both usable reconstructions together, matching Audacity's basic mix."""
    mixed = stitched_region + silence_region

    peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0

    if peak > 1.0:
        mixed = mixed / peak

    return mixed.astype(np.float32, copy=False)


def apply_edits(
    stitched_audio: np.ndarray,
    silence_based_audio: np.ndarray,
    edits: list[Edit],
    sample_rate: int,
):
    output = stitched_audio.copy()

    stats = Counter()

    for edit in edits:
        start_sample = seconds_to_sample(edit.start, sample_rate)
        end_sample = seconds_to_sample(edit.end, sample_rate)

        # Protect against tiny rounding differences.
        start_sample = max(0, start_sample)
        end_sample = min(end_sample, len(output))

        if end_sample <= start_sample:
            print(
                f"WARNING: CSV line {edit.line_number} "
                f"resulted in an empty sample range. Skipping."
            )
            stats["skipped"] += 1
            continue

        print(
            f"{edit.start:10.6f}s -> {edit.end:10.6f}s | "
            f"{edit.action.upper():24} | {edit.note}"
        )

        if edit.action == "take 2":
            # Make sure the alternate track contains this region.
            if end_sample > len(silence_based_audio):
                raise ValueError(
                    f"CSV line {edit.line_number}: "
                    f"Track 2 does not contain enough audio "
                    f"for this edit."
                )

            output[start_sample:end_sample] = (
                silence_based_audio[start_sample:end_sample]
            )

            stats["take 2"] += 1

        elif edit.action == "clear":
            output[start_sample:end_sample] = 0
            stats["clear"] += 1

        elif edit.action == "combine":
            if end_sample > len(silence_based_audio):
                raise ValueError(
                    f"CSV line {edit.line_number}: "
                    f"Track 2 does not contain enough audio "
                    f"for this edit."
                )

            stitched_region = output[start_sample:end_sample].copy()
            silence_region = silence_based_audio[start_sample:end_sample]

            mixed_region = combine_audio(
                stitched_region,
                silence_region,
            )

            apply_boundary_crossfades(
                output=output,
                mixed_region=mixed_region,
                start_sample=start_sample,
                end_sample=end_sample,
                sample_rate=sample_rate,
            )

            stats["combine"] += 1

        elif edit.action == "further analysis needed":
            # Leave stitched audio unchanged.
            stats["analysis pending"] += 1

        else:
            print(
                f"WARNING: Unknown action '{edit.action}' "
                f"on CSV line {edit.line_number}. "
                f"Leaving stitched audio unchanged."
            )
            stats["unknown"] += 1

    return output, stats


def main():
    parser = argparse.ArgumentParser(
        description="Apply the Junkyard Wars restoration edit map."
    )

    parser.add_argument(
        "--edit-map",
        required=True,
        type=Path,
        help="CSV containing start, end, action, and note columns.",
    )

    parser.add_argument(
        "--stitched",
        required=True,
        type=Path,
        help="Primary stitched reconstruction WAV.",
    )

    parser.add_argument(
        "--silence-based",
        required=True,
        type=Path,
        help="Alternate silence-based reconstruction WAV.",
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output WAV path.",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("JUNKYARD WARS RESTORATION - EDIT MAP APPLIER")
    print("=" * 70)

    if not args.edit_map.exists():
        raise FileNotFoundError(
            f"Edit map not found: {args.edit_map}"
        )

    if not args.stitched.exists():
        raise FileNotFoundError(
            f"Stitched audio not found: {args.stitched}"
        )

    if not args.silence_based.exists():
        raise FileNotFoundError(
            f"Silence-based audio not found: {args.silence_based}"
        )

    print()
    print("Loading edit map...")

    edits = load_edit_map(args.edit_map)

    action_counts = Counter(edit.action for edit in edits)

    print(f"Edit entries: {len(edits)}")

    for action in sorted(action_counts):
        print(f"  {action}: {action_counts[action]}")

    print()
    print("Reading audio information...")

    stitched_info = get_audio_info(args.stitched)
    silence_info = get_audio_info(args.silence_based)

    print()
    print_audio_info("Stitched audio", stitched_info)

    print()
    print_audio_info("Silence-based audio", silence_info)

    print()
    print("Validating audio compatibility...")

    validate_audio(stitched_info, silence_info)

    duration_difference = (
        silence_info["duration"] - stitched_info["duration"]
    )

    print("Audio formats are compatible.")
    print(
        f"Duration difference: {duration_difference:+.6f}s"
    )

    print()
    print("Validating edit map...")

    validate_edits(
        edits,
        stitched_info["duration"],
    )

    print("Edit map validation passed.")

    print()
    print("Loading stitched audio...")

    stitched_audio, stitched_sample_rate = sf.read(
        args.stitched,
        dtype="float32",
        always_2d=True,
    )

    print("Loading silence-based audio...")

    silence_audio, silence_sample_rate = sf.read(
        args.silence_based,
        dtype="float32",
        always_2d=True,
    )

    if silence_sample_rate != stitched_sample_rate:
        print(
            f"Resampling silence-based audio: "
            f"{silence_sample_rate} Hz -> "
            f"{stitched_sample_rate} Hz"
        )

        # librosa expects samples on the final axis.
        # soundfile gives us (frames, channels), so transpose.
        silence_audio = librosa.resample(
            silence_audio.T,
            orig_sr=silence_sample_rate,
            target_sr=stitched_sample_rate,
            res_type="soxr_hq",
        ).T

        silence_sample_rate = stitched_sample_rate

        print(
            f"Resampled silence-based audio: "
            f"{len(silence_audio) / silence_sample_rate:.6f}s"
        )

    print()
    print("Applying edits...")
    print("-" * 70)

    output_audio, applied_stats = apply_edits(
        stitched_audio=stitched_audio,
        silence_based_audio=silence_audio,
        edits=edits,
        sample_rate=stitched_sample_rate,
    )

    print("-" * 70)

    print()
    print("Writing output...")

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Preserve the stitched source subtype where possible.
    sf.write(
        args.output,
        output_audio,
        stitched_sample_rate,
        subtype=stitched_info["subtype"],
    )

    print()
    print("=" * 70)
    print("COMPLETE")
    print("=" * 70)

    print(f"Output: {args.output}")
    print(
        f"Output duration: "
        f"{len(output_audio) / stitched_sample_rate:.6f}s"
    )

    print()
    print("Operations performed:")

    for action, count in sorted(applied_stats.items()):
        print(f"  {action}: {count}")


if __name__ == "__main__":
    main()
