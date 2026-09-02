from pathlib import Path
import json

import numpy as np
import soundfile as sf


# ============================================================
# Configuration
# ============================================================

REVIEW_FOLDER = Path("review")

PADDING_MS = 250

RUNS = [
    "20s",
    "30s",
    "45s",
    "60s",
]


# ============================================================
# Metadata
# ============================================================

def load_segment_metadata(folder: Path):

    filename = folder / "metadata.json"

    with open(
        filename,
        "r",
        encoding="utf8"
    ) as f:

        return json.load(f)


# ============================================================
# Review folders
# ============================================================

def find_review_folders():

    folders = []

    for folder in REVIEW_FOLDER.iterdir():

        if not folder.is_dir():
            continue

        try:
            index = int(folder.name)
        except ValueError:
            continue

        folders.append(
            (index, folder)
        )

    folders.sort(
        key=lambda x: x[0]
    )

    return [
        folder
        for _, folder in folders
    ]


# ============================================================
# Stitch one run
# ============================================================

def stitch_run(
    run_name: str,
    folders: list[Path],
):

    print()
    print("=" * 70)
    print(f"Reconstructing {run_name}")
    print("=" * 70)

    output_file = (
        REVIEW_FOLDER /
        f"{run_name}_full.wav"
    )

    sample_rate = None
    padding_samples = None

    output = None

    previous_end_sample = 0

    for position, folder in enumerate(folders):

        audio_file = (
            folder /
            f"{run_name}.wav"
        )

        if not audio_file.exists():

            raise FileNotFoundError(
                f"Missing: {audio_file}"
            )

        metadata = load_segment_metadata(
            folder
        )

        segment_id = metadata["id"]

        start_time = float(
            metadata["start"]
        )

        end_time = float(
            metadata["end"]
        )

        duration = float(
            metadata["duration"]
        )

        # ----------------------------------------------------
        # Load audio
        # ----------------------------------------------------

        audio, sr = sf.read(
            audio_file
        )

        audio = audio.astype(
            np.float32
        )

        # ----------------------------------------------------
        # Sample rate
        # ----------------------------------------------------

        if sample_rate is None:

            sample_rate = sr

            padding_samples = int(
                round(
                    sample_rate *
                    PADDING_MS /
                    1000
                )
            )

            # We don't know the final length yet.
            # Create the output dynamically below.

        elif sr != sample_rate:

            raise RuntimeError(
                f"Sample-rate mismatch in "
                f"{audio_file}: "
                f"{sr} Hz, expected "
                f"{sample_rate} Hz."
            )

        # ----------------------------------------------------
        # Remove the 250ms padding from BOTH sides.
        #
        # extract_segments.py always created:
        #
        #     start - 250ms
        #     actual segment
        #     end + 250ms
        #
        # So every review WAV contains padding on both ends.
        # ----------------------------------------------------

        if len(audio) <= padding_samples * 2:

            raise RuntimeError(
                f"Segment {folder.name} is too short "
                f"to remove {PADDING_MS}ms padding "
                f"from both ends."
            )

        trimmed = audio[
            padding_samples:
            -padding_samples
        ]

        # ----------------------------------------------------
        # Verify duration
        # ----------------------------------------------------

        expected_samples = int(
            round(
                duration *
                sample_rate
            )
        )

        actual_samples = len(trimmed)

        difference = (
            actual_samples -
            expected_samples
        )

        if abs(difference) > 2:

            print()

            print(
                f"WARNING: Segment {folder.name}"
            )

            print(
                f"  Expected: "
                f"{expected_samples:,} samples"
            )

            print(
                f"  Actual:   "
                f"{actual_samples:,} samples"
            )

            print(
                f"  Difference: "
                f"{difference:+,} samples"
            )

        # ----------------------------------------------------
        # Convert timeline position to samples
        # ----------------------------------------------------

        start_sample = int(
            round(
                start_time *
                sample_rate
            )
        )

        end_sample = int(
            round(
                end_time *
                sample_rate
            )
        )

        timeline_samples = (
            end_sample -
            start_sample
        )

        # ----------------------------------------------------
        # Verify timeline duration
        # ----------------------------------------------------

        if abs(
            timeline_samples -
            actual_samples
        ) > 2:

            print()

            print(
                f"WARNING: Timeline/audio mismatch "
                f"for {folder.name}"
            )

            print(
                f"  Timeline: "
                f"{timeline_samples:,} samples"
            )

            print(
                f"  Audio:    "
                f"{actual_samples:,} samples"
            )

        # ----------------------------------------------------
        # Create output buffer when we know the channel layout.
        # ----------------------------------------------------

        if output is None:

            # Make the output long enough for the entire
            # timeline. We'll extend it if necessary.

            if audio.ndim == 1:

                output = np.zeros(
                    end_sample,
                    dtype=np.float32
                )

            else:

                output = np.zeros(
                    (
                        end_sample,
                        audio.shape[1]
                    ),
                    dtype=np.float32
                )

        # ----------------------------------------------------
        # Extend output if necessary.
        # ----------------------------------------------------

        required_length = end_sample

        if required_length > len(output):

            additional = (
                required_length -
                len(output)
            )

            if output.ndim == 1:

                output = np.pad(
                    output,
                    (0, additional)
                )

            else:

                output = np.pad(
                    output,
                    (
                        (0, additional),
                        (0, 0)
                    )
                )

        # ----------------------------------------------------
        # Detect gaps and overlaps.
        # ----------------------------------------------------

        if start_sample > previous_end_sample:

            gap_samples = (
                start_sample -
                previous_end_sample
            )

            gap_seconds = (
                gap_samples /
                sample_rate
            )

            print()

            print(
                f"  Gap before {folder.name}: "
                f"{gap_seconds:.3f}s"
            )

        elif start_sample < previous_end_sample:

            overlap_samples = (
                previous_end_sample -
                start_sample
            )

            overlap_seconds = (
                overlap_samples /
                sample_rate
            )

            print()

            print(
                f"  WARNING: Timeline overlap before "
                f"{folder.name}: "
                f"{overlap_seconds:.3f}s"
            )

        # ----------------------------------------------------
        # Put the actual segment into its exact timeline
        # position.
        #
        # The output buffer starts as silence, so any gaps
        # remain silence automatically.
        # ----------------------------------------------------

        destination_end = (
            start_sample +
            len(trimmed)
        )

        if destination_end > len(output):

            additional = (
                destination_end -
                len(output)
            )

            if output.ndim == 1:

                output = np.pad(
                    output,
                    (0, additional)
                )

            else:

                output = np.pad(
                    output,
                    (
                        (0, additional),
                        (0, 0)
                    )
                )

        output[
            start_sample:
            destination_end
        ] = trimmed

        previous_end_sample = max(
            previous_end_sample,
            end_sample
        )

        print(
            f"\r  {position + 1:3d}/"
            f"{len(folders)} "
            f"{folder.name} "
            f"{start_time:.3f}s -> "
            f"{end_time:.3f}s",
            end="",
        )

    print()

    # ========================================================
    # Write reconstructed audio
    # ========================================================

    if output is None:

        raise RuntimeError(
            "No audio was reconstructed."
        )

    print()
    print("Writing reconstructed audio...")

    sf.write(
        output_file,
        output,
        sample_rate
    )

    duration = (
        len(output) /
        sample_rate
    )

    print()
    print(
        f"Output    : {output_file}"
    )

    print(
        f"Samples   : {len(output):,}"
    )

    print(
        f"Sample rate: {sample_rate:,} Hz"
    )

    print(
        f"Duration   : {duration:.3f}s"
    )

    print(
        f"Duration   : "
        f"{int(duration // 60):02d}:"
        f"{duration % 60:06.3f}"
    )

    print("Done.")

    return output_file


# ============================================================
# Main
# ============================================================

def main():

    if not REVIEW_FOLDER.exists():

        raise RuntimeError(
            f"Review folder does not exist: "
            f"{REVIEW_FOLDER}"
        )

    folders = find_review_folders()

    if not folders:

        raise RuntimeError(
            "No numbered review folders found."
        )

    print(
        f"Found {len(folders)} review folders."
    )

    print(
        f"First: {folders[0].name}"
    )

    print(
        f"Last : {folders[-1].name}"
    )

    # --------------------------------------------------------
    # Verify expected folder range
    # --------------------------------------------------------

    expected_ids = list(
        range(337)
    )

    actual_ids = [
        int(folder.name)
        for folder in folders
    ]

    if actual_ids != expected_ids:

        missing = sorted(
            set(expected_ids) -
            set(actual_ids)
        )

        unexpected = sorted(
            set(actual_ids) -
            set(expected_ids)
        )

        if missing:

            print(
                f"\nMissing folders: "
                f"{missing}"
            )

        if unexpected:

            print(
                f"\nUnexpected folders: "
                f"{unexpected}"
            )

        raise RuntimeError(
            "Review folder sequence is not "
            "0000 through 0336."
        )

    # --------------------------------------------------------
    # Reconstruct all runs
    # --------------------------------------------------------

    for run_name in RUNS:

        stitch_run(
            run_name,
            folders
        )

    print()
    print("=" * 70)
    print("ALL RUNS RECONSTRUCTED")
    print("=" * 70)


if __name__ == "__main__":
    main()