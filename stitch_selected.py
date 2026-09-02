import argparse
import json
import sys
from pathlib import Path
from dataclasses import dataclass
import soundfile as sf
import numpy as np

REVIEW_PADDING_SECONDS = 0.250

@dataclass
class StitchPlanItem:
    segment_id: int
    selected_run: str
    audio_path: Path
    start_seconds: float
    end_seconds: float
    duration_seconds: float

def load_json(path: Path):
    """Load a JSON file and return its contents."""
    try:
        with open(path, "r", encoding="utf-8-sig") as file:
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Required file not found: {path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def normalize_run_name(value):
    """
    Normalize a selected run name.

    Examples:
        20   -> 20s
        20s  -> 20s
        20S  -> 20s
    """

    value = str(value).strip().lower()

    if value.endswith(".wav"):
        value = value[:-4]

    if value.endswith("s"):
        return value

    return f"{value}s"


def get_choice_map(choices_data):
    """
    Convert choices.json into:

        {
            segment_number: selected_run
        }
    """

    choices = {}

    if not isinstance(choices_data, list):
        raise ValueError(
            "choices.json should contain a JSON array of choices."
        )

    for entry in choices_data:

        if not isinstance(entry, dict):
            continue

        segment_id = entry.get("SegmentId")
        selected_run = entry.get("SelectedRun")
        status = entry.get("Status")

        if segment_id is None:
            print(
                "[WARNING] Found a choice entry with no SegmentId."
            )
            continue

        if not selected_run:
            print(
                f"[WARNING] Segment {segment_id} "
                "has no SelectedRun."
            )
            continue

        # Status 1 represents a completed/reviewed selection.
        if status != 1:
            print(
                f"[WARNING] Segment {segment_id} "
                f"has Status={status}; skipping."
            )
            continue

        try:
            segment_number = int(segment_id)
        except (ValueError, TypeError):
            print(
                f"[WARNING] Invalid SegmentId: {segment_id}"
            )
            continue

        choices[segment_number] = normalize_run_name(
            selected_run
        )

    return choices


def get_segment_directories(review_folder: Path):
    """
    Return numbered segment directories in numerical order.
    """

    segment_dirs = []

    for path in review_folder.iterdir():

        if not path.is_dir():
            continue

        if not path.name.isdigit():
            continue

        segment_dirs.append(path)

    return sorted(segment_dirs, key=lambda p: int(p.name))


def validate_segment(segment_dir: Path, selected_run: str):
    """
    Validate the files required for one selected segment.
    """

    metadata_path = segment_dir / "metadata.json"
    comparison_path = segment_dir / "comparison.json"

    audio_path = segment_dir / f"{selected_run}.wav"

    errors = []

    if not metadata_path.exists():
        errors.append("metadata.json is missing")

    if not comparison_path.exists():
        errors.append("comparison.json is missing")

    if not audio_path.exists():
        errors.append(f"{audio_path.name} is missing")

    return errors


def load_segment_metadata(segment_dir: Path):
    """
    Load metadata.json for a segment.
    """

    metadata_path = segment_dir / "metadata.json"

    return load_json(metadata_path)


def validate_project(root: Path):
    """
    Validate the overall project structure.

    Returns:

        choices
        segment_dirs
    """

    choices_path = root / "choices.json"
    project_path = root / "project.json"
    review_folder = root / "review"

    print()
    print("=" * 60)
    print("VALIDATING PROJECT")
    print("=" * 60)

    if not root.exists():
        raise FileNotFoundError(
            f"Project root does not exist: {root}"
        )

    if not choices_path.exists():
        raise FileNotFoundError(
            f"choices.json not found: {choices_path}"
        )

    if not project_path.exists():
        raise FileNotFoundError(
            f"project.json not found: {project_path}"
        )

    if not review_folder.exists():
        raise FileNotFoundError(
            f"review folder not found: {review_folder}"
        )

    print(f"Project root: {root}")
    print(f"Choices:      {choices_path}")
    print(f"Project:      {project_path}")
    print(f"Review:       {review_folder}")

    choices_data = load_json(choices_path)
    project_data = load_json(project_path)

    choices = get_choice_map(choices_data)

    print()
    print(f"Choices loaded: {len(choices)}")

    segment_dirs = get_segment_directories(review_folder)

    print(f"Segments found: {len(segment_dirs)}")

    if not segment_dirs:
        raise RuntimeError(
            "No numbered segment directories were found."
        )

    print()
    print("-" * 60)
    print("VALIDATING SEGMENTS")
    print("-" * 60)

    errors_found = 0

    for segment_dir in segment_dirs:

        segment_number = int(segment_dir.name)

        if segment_number not in choices:

            print(
                f"[WARNING] Segment {segment_dir.name}: "
                f"No selection found in choices.json"
            )

            errors_found += 1
            continue

        selected_run = choices[segment_number]

        errors = validate_segment(
            segment_dir,
            selected_run
        )

        if errors:

            print(
                f"[ERROR] Segment {segment_dir.name} "
                f"({selected_run})"
            )

            for error in errors:
                print(f"    - {error}")

            errors_found += 1

        else:

            print(
                f"[OK] {segment_dir.name} "
                f"→ {selected_run}.wav"
            )

    print()
    print("=" * 60)

    if errors_found:

        print(
            f"VALIDATION COMPLETED WITH "
            f"{errors_found} ISSUE(S)"
        )

    else:

        print("VALIDATION SUCCESSFUL")

    print("=" * 60)
    print()

    return choices, segment_dirs

def get_metadata_value(metadata, *names):
    """
    Return the first matching metadata value.

    The lookup supports several possible key spellings so we can
    produce a useful error if a metadata file is malformed.
    """

    for name in names:
        if name in metadata:
            return metadata[name]

    return None


def get_segment_timing(metadata, metadata_path: Path):
    """
    Extract the original timeline position for a review segment.

    Returns:
        start_seconds
        end_seconds
    """

    start = get_metadata_value(
        metadata,
        "start",
        "start_time",
        "start_seconds",
        "segment_start"
    )

    end = get_metadata_value(
        metadata,
        "end",
        "end_time",
        "end_seconds",
        "segment_end"
    )

    if start is None or end is None:
        raise ValueError(
            f"Could not find start/end timing in {metadata_path}. "
            f"Available keys: {', '.join(metadata.keys())}"
        )

    try:
        start = float(start)
        end = float(end)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Invalid timing values in {metadata_path}: "
            f"start={start!r}, end={end!r}"
        ) from exc

    if end <= start:
        raise ValueError(
            f"Invalid timing in {metadata_path}: "
            f"end ({end}) must be greater than start ({start})"
        )

    return start, end

def build_stitch_plan(choices, segment_dirs):
    """
    Build a chronological plan describing exactly which selected
    WAV file belongs at each point in the original timeline.
    """

    plan = []

    for segment_dir in segment_dirs:

        segment_id = int(segment_dir.name)

        if segment_id not in choices:
            raise ValueError(
                f"No choice exists for segment {segment_id}."
            )

        selected_run = choices[segment_id]

        metadata_path = segment_dir / "metadata.json"
        metadata = load_segment_metadata(segment_dir)

        start_seconds, end_seconds = get_segment_timing(
            metadata,
            metadata_path
        )

        audio_path = (
            segment_dir /
            f"{selected_run}.wav"
        )

        if not audio_path.exists():
            raise FileNotFoundError(
                f"Selected audio file not found: {audio_path}"
            )

        plan.append(
            StitchPlanItem(
                segment_id=segment_id,
                selected_run=selected_run,
                audio_path=audio_path,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                duration_seconds=end_seconds - start_seconds
            )
        )

    # Segment folder numbers should already be chronological, but
    # the metadata timeline is the source of truth.
    plan.sort(
        key=lambda item: item.start_seconds
    )

    return plan

def format_timestamp(seconds: float):
    """
    Format seconds as HH:MM:SS.mmm.
    """

    total_milliseconds = round(seconds * 1000)

    hours = total_milliseconds // 3_600_000
    remaining = total_milliseconds % 3_600_000

    minutes = remaining // 60_000
    remaining %= 60_000

    whole_seconds = remaining // 1_000
    milliseconds = remaining % 1_000

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{whole_seconds:02d}."
        f"{milliseconds:03d}"
    )

def print_stitch_plan(plan):
    """
    Print the complete stitching plan.
    """

    print()
    print("=" * 100)
    print("STITCHING PLAN")
    print("=" * 100)

    print(
        f"{'Segment':<10}"
        f"{'Run':<8}"
        f"{'Start':<16}"
        f"{'End':<16}"
        f"{'Duration':<12}"
        f"File"
    )

    print("-" * 100)

    previous_end = None

    for item in plan:

        gap_text = ""

        if previous_end is not None:

            gap = (
                item.start_seconds -
                previous_end
            )

            if gap > 0.001:
                gap_text = (
                    f"  GAP: {gap:.3f}s"
                )

            elif gap < -0.001:
                gap_text = (
                    f"  OVERLAP: {abs(gap):.3f}s"
                )

        print(
            f"{item.segment_id:04d}      "
            f"{item.selected_run:<8}"
            f"{format_timestamp(item.start_seconds):<16}"
            f"{format_timestamp(item.end_seconds):<16}"
            f"{item.duration_seconds:>8.3f}s   "
            f"{item.audio_path.name}"
            f"{gap_text}"
        )

        previous_end = item.end_seconds

    print("-" * 100)

    if plan:

        total_start = plan[0].start_seconds
        total_end = max(
            item.end_seconds
            for item in plan
        )

        print(
            f"Segments: {len(plan)}"
        )

        print(
            f"Timeline start: "
            f"{format_timestamp(total_start)}"
        )

        print(
            f"Timeline end:   "
            f"{format_timestamp(total_end)}"
        )

        print(
            f"Covered span:   "
            f"{total_end - total_start:.3f}s"
        )

    print("=" * 100)
    print()


def validate_stitch_plan(plan):
    """
    Validate chronological ordering and report significant gaps
    or overlaps.

    Does not reject gaps or overlaps because silence-based
    segmentation may legitimately contain either.
    """

    if not plan:
        raise ValueError(
            "Stitch plan is empty."
        )

    warnings = []

    previous_item = None

    for item in plan:

        if previous_item is not None:

            difference = (
                item.start_seconds -
                previous_item.end_seconds
            )

            # Large gaps or overlaps are worth reporting.
            if difference > 1.0:

                warnings.append(
                    f"Large gap between segment "
                    f"{previous_item.segment_id:04d} "
                    f"and {item.segment_id:04d}: "
                    f"{difference:.3f}s"
                )

            elif difference < -1.0:

                warnings.append(
                    f"Large overlap between segment "
                    f"{previous_item.segment_id:04d} "
                    f"and {item.segment_id:04d}: "
                    f"{abs(difference):.3f}s"
                )

        previous_item = item

    return warnings

def inspect_audio_file(audio_path: Path):
    """
    Read audio metadata without loading the entire WAV into memory.
    """

    try:
        info = sf.info(audio_path)
    except Exception as exc:
        raise RuntimeError(
            f"Could not read audio file: {audio_path}"
        ) from exc

    return {
        "sample_rate": info.samplerate,
        "channels": info.channels,
        "frames": info.frames,
        "duration_seconds": info.frames / info.samplerate
    }

def validate_audio_files(plan):
    """
    Validate all selected audio files.

    Returns the common audio format:

        {
            "sample_rate": ...,
            "channels": ...
        }

    Raises an error if incompatible audio formats are found.
    """

    print()
    print("=" * 100)
    print("VALIDATING SELECTED AUDIO FILES")
    print("=" * 100)

    expected_sample_rate = None
    expected_channels = None

    duration_warnings = []
    format_errors = []

    for index, item in enumerate(plan):

        info = inspect_audio_file(item.audio_path)

        sample_rate = info["sample_rate"]
        channels = info["channels"]
        frames = info["frames"]
        actual_duration = info["duration_seconds"]

        if expected_sample_rate is None:
            expected_sample_rate = sample_rate
            expected_channels = channels

        if sample_rate != expected_sample_rate:
            format_errors.append(
                f"Segment {item.segment_id:04d}: "
                f"sample rate is {sample_rate}, "
                f"expected {expected_sample_rate}"
            )

        if channels != expected_channels:
            format_errors.append(
                f"Segment {item.segment_id:04d}: "
                f"channels is {channels}, "
                f"expected {expected_channels}"
            )

        expected_duration = item.duration_seconds

        duration_difference = abs(
            actual_duration - expected_duration
        )

        print(
            f"{item.segment_id:04d}  "
            f"{item.selected_run:<4}  "
            f"{sample_rate:>6} Hz  "
            f"{channels} ch  "
            f"{frames:>10,} frames  "
            f"actual={actual_duration:8.3f}s  "
            f"timeline={expected_duration:8.3f}s  "
            f"diff={duration_difference:.6f}s"
        )

        # Review clips intentionally include 0.5 seconds of padding.
        EXPECTED_PADDING_SECONDS = 0.5

        duration_difference = (
            actual_duration - expected_duration
        )

        if abs(duration_difference - EXPECTED_PADDING_SECONDS) > 0.010:
            duration_warnings.append(
                {
                    "segment_id": item.segment_id,
                    "expected": expected_duration,
                    "actual": actual_duration,
                    "difference": duration_difference,
                    "audio_path": item.audio_path
                }
            )

    print("-" * 100)

    if format_errors:

        print()
        print("FORMAT ERRORS:")

        for error in format_errors:
            print(f"[ERROR] {error}")

        raise RuntimeError(
            "Selected audio files do not have a compatible "
            "sample rate and channel count."
        )

    print()
    print(
        f"Common sample rate: {expected_sample_rate} Hz"
    )

    print(
        f"Common channels:    {expected_channels}"
    )

    print(
        f"Files validated:    {len(plan)}"
    )

    print("=" * 100)

    if duration_warnings:

        print()
        print(
            f"DURATION WARNINGS: "
            f"{len(duration_warnings)}"
        )

        print("-" * 100)

        for warning in duration_warnings:

            print(
                f"[WARNING] "
                f"Segment {warning['segment_id']:04d}: "
                f"timeline={warning['expected']:.3f}s, "
                f"audio={warning['actual']:.3f}s, "
                f"diff={warning['difference']:.3f}s"
            )

    else:

        print()
        print(
            "ALL AUDIO DURATIONS MATCH "
            "THE TIMELINE WITHIN TOLERANCE."
        )

    print()

    return {
        "sample_rate": expected_sample_rate,
        "channels": expected_channels,
        "duration_warnings": duration_warnings
    }

def get_clip_start_sample(item, sample_rate):
    """
    Calculate where a padded review clip belongs on the
    reconstructed timeline.

    Review clips contain 250 ms of context before the metadata
    segment start.
    """

    clip_start_seconds = (
        item.start_seconds -
        REVIEW_PADDING_SECONDS
    )

    # A clip near the beginning of the source could have its
    # padding clamped to zero.
    clip_start_seconds = max(
        0.0,
        clip_start_seconds
    )

    return round(
        clip_start_seconds * sample_rate
    )

def get_output_frame_count(plan, sample_rate):
    """
    Determine the number of frames required to contain every
    selected review clip.
    """

    maximum_end_sample = 0

    for item in plan:

        clip_start_sample = get_clip_start_sample(
            item,
            sample_rate
        )

        info = sf.info(item.audio_path)

        clip_end_sample = (
            clip_start_sample +
            info.frames
        )

        maximum_end_sample = max(
            maximum_end_sample,
            clip_end_sample
        )

    return maximum_end_sample

def equal_power_crossfade(
    existing,
    incoming
):
    """
    Blend two equally sized overlapping audio regions using an
    equal-power crossfade.
    """

    if len(existing) != len(incoming):
        raise ValueError(
            "Crossfade regions must have equal lengths."
        )

    length = len(existing)

    if length == 0:
        return existing

    positions = np.linspace(
        0.0,
        np.pi / 2.0,
        length,
        endpoint=True
    )

    fade_out = np.cos(positions)
    fade_in = np.sin(positions)

    return (
        existing * fade_out +
        incoming * fade_in
    )


def build_audio_timeline(
    plan,
    sample_rate
):
    """
    Create the reconstructed audio timeline from the selected
    review clips.

    The returned array is mono float32 audio.

    This function does not write any files.
    """

    print()
    print("=" * 100)
    print("BUILDING AUDIO TIMELINE")
    print("=" * 100)

    output_frames = get_output_frame_count(
        plan,
        sample_rate
    )

    output = np.zeros(
        output_frames,
        dtype=np.float32
    )

    occupied = np.zeros(
        output_frames,
        dtype=bool
    )

    print(
        f"Output frames: {output_frames:,}"
    )

    print(
        f"Output duration: "
        f"{output_frames / sample_rate:.3f}s"
    )

    print()

    overlap_count = 0

    for index, item in enumerate(plan, start=1):

        audio, file_sample_rate = sf.read(
            item.audio_path,
            dtype="float32"
        )

        if file_sample_rate != sample_rate:
            raise ValueError(
                f"Segment {item.segment_id:04d} has "
                f"sample rate {file_sample_rate}, "
                f"expected {sample_rate}."
            )

        # Safety check in case SoundFile returns a 2D array.
        if audio.ndim > 1:

            if audio.shape[1] != 1:
                raise ValueError(
                    f"Segment {item.segment_id:04d} "
                    f"is not mono."
                )

            audio = audio[:, 0]

        start_sample = get_clip_start_sample(
            item,
            sample_rate
        )

        end_sample = (
            start_sample +
            len(audio)
        )

        if end_sample > len(output):
            raise ValueError(
                f"Segment {item.segment_id:04d} "
                f"extends beyond the output timeline."
            )

        existing = output[
            start_sample:end_sample
        ]

        existing_occupied = occupied[
            start_sample:end_sample
        ]

        if np.any(existing_occupied):

            overlap_count += 1

            overlap_mask = existing_occupied

            # Non-overlapping portion can be copied directly.
            new_region = existing.copy()

            # Find contiguous regions of overlap so each one
            # can be crossfaded independently.
            mask_changes = np.diff(
                overlap_mask.astype(np.int8)
            )

            starts = list(
                np.where(mask_changes == 1)[0] + 1
            )

            ends = list(
                np.where(mask_changes == -1)[0] + 1
            )

            if overlap_mask[0]:
                starts.insert(0, 0)

            if overlap_mask[-1]:
                ends.append(len(overlap_mask))

            # Copy all non-overlapping samples.
            new_region[
                ~overlap_mask
            ] = audio[
                ~overlap_mask
            ]

            # Crossfade each overlapping region.
            for overlap_start, overlap_end in zip(
                starts,
                ends
            ):

                new_region[
                    overlap_start:overlap_end
                ] = equal_power_crossfade(
                    existing[
                        overlap_start:overlap_end
                    ],
                    audio[
                        overlap_start:overlap_end
                    ]
                )

            output[
                start_sample:end_sample
            ] = new_region

        else:

            output[
                start_sample:end_sample
            ] = audio

        occupied[
            start_sample:end_sample
        ] = True

        print(
            f"[{index:03d}/{len(plan):03d}] "
            f"Segment {item.segment_id:04d} → "
            f"{item.selected_run}.wav"
        )

    print()
    print("-" * 100)

    print(
        f"Segments placed: {len(plan)}"
    )

    print(
        f"Overlapping placements: "
        f"{overlap_count}"
    )

    print(
        f"Final timeline duration: "
        f"{len(output) / sample_rate:.3f}s"
    )

    print("=" * 100)
    print()

    return output

def write_final_audio(
    timeline,
    sample_rate,
    output_path: Path
):
    """
    Write the reconstructed timeline to a WAV file and validate
    the result after writing.
    """

    print()
    print("=" * 100)
    print("WRITING FINAL AUDIO")
    print("=" * 100)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    print(f"Output: {output_path}")
    print(f"Sample rate: {sample_rate} Hz")
    print(f"Channels: mono")
    print(f"Frames: {len(timeline):,}")
    print(
        f"Duration: "
        f"{len(timeline) / sample_rate:.3f}s"
    )

    print()
    print("Writing WAV...")

    sf.write(
        output_path,
        timeline,
        sample_rate,
        subtype="FLOAT"
    )

    print("Write complete.")

    print()
    print("Validating written file...")

    info = sf.info(output_path)

    expected_frames = len(timeline)

    errors = []

    if info.samplerate != sample_rate:
        errors.append(
            f"Sample rate mismatch: "
            f"expected {sample_rate}, "
            f"got {info.samplerate}"
        )

    if info.channels != 1:
        errors.append(
            f"Channel mismatch: "
            f"expected 1, "
            f"got {info.channels}"
        )

    if info.frames != expected_frames:
        errors.append(
            f"Frame count mismatch: "
            f"expected {expected_frames:,}, "
            f"got {info.frames:,}"
        )

    if errors:

        print()
        print("VALIDATION FAILED")

        for error in errors:
            print(f"[ERROR] {error}")

        raise RuntimeError(
            "Final WAV validation failed."
        )

    print()

    print("FINAL WAV VALIDATION SUCCESSFUL")

    print(f"Sample rate: {info.samplerate} Hz")
    print(f"Channels:    {info.channels}")
    print(f"Frames:      {info.frames:,}")
    print(
        f"Duration:    "
        f"{info.frames / info.samplerate:.3f}s"
    )

    print("=" * 100)
    print()

    return output_path

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Validate a Junkyard Restoration Studio project "
            "before stitching selected audio segments."
        )
    )

    parser.add_argument(
        "project_root",
        type=Path,
        help=(
            "Path containing choices.json, project.json, "
            "and the review folder."
        )
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("stitched_selected.wav"),
        help=(
           "Output path for the final stitched WAV. "
            "Defaults to stitched_selected.wav."
        )
    )

    args = parser.parse_args()

    try:

        root = args.project_root.resolve()

        choices, segment_dirs = validate_project(
            root
        )

        plan = build_stitch_plan(
            choices,
            segment_dirs
        )

        warnings = validate_stitch_plan(
         plan
        )

        print_stitch_plan(
         plan
        )

        if warnings:

            print("PLAN WARNINGS")

            print("-" * 60)

            for warning in warnings:
              print(f"[WARNING] {warning}")

            print("-" * 60)
            print()

        else:

            print(
                 "STITCH PLAN VALIDATION SUCCESSFUL"
             )
            print()

        audio_format = validate_audio_files(plan)
        timeline = build_audio_timeline(
            plan,
            audio_format["sample_rate"]
        )

        output_path = args.output.resolve()

        write_final_audio(
            timeline,
            audio_format["sample_rate"],
            output_path
        )

    except Exception as exc:

        print()
        print("ERROR")
        print("=" * 60)
        print(exc)
        print("=" * 60)

        sys.exit(1)


if __name__ == "__main__":
    main()