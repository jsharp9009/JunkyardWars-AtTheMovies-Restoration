"""
Junkyard Wars Audio Separation
Stitcher
Version 1 - Part 1

Loads metadata and verifies chunk files.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
import json

import numpy as np
import soundfile as sf


# ============================================================
# Configuration
# ============================================================

OUTPUT_DIR = Path("output")

METADATA_FILE = OUTPUT_DIR / "metadata.json"

OUTPUT_SPEAKER1 = OUTPUT_DIR / "speaker1_full.wav"

OUTPUT_SPEAKER2 = OUTPUT_DIR / "speaker2_full.wav"


# ============================================================
# Metadata
# ============================================================

@dataclass
class ChunkInfo:

    index: int

    start_sample: int

    end_sample: int

    start_seconds: float

    end_seconds: float

    status: str

    processing_time: float | None

    speaker1_file: str | None

    speaker2_file: str | None

    error: str | None = None


class Metadata:

    def __init__(self, filename: Path):

        self.filename = filename

        self.data = {}

    def load(self):

        with open(self.filename, "r", encoding="utf8") as f:

            self.data = json.load(f)

    @property
    def sample_rate(self):

        return self.data["sample_rate"]

    @property
    def overlap_seconds(self):

        return self.data["overlap_seconds"]

    @property
    def chunk_seconds(self):

        return self.data["chunk_seconds"]

    @property
    def chunks(self):

        return [
            ChunkInfo(**c)
            for c in self.data["chunks"]
        ]


# ============================================================
# Verification
# ============================================================

def verify_chunks(metadata: Metadata):

    print("Verifying chunk files...")

    failed = False

    for chunk in metadata.chunks:

        if chunk.status != "complete":

            print(
                f"Chunk {chunk.index:04d} "
                f"is '{chunk.status}'."
            )

            failed = True

            continue

        if not Path(chunk.speaker1_file).exists():

            print(
                f"Missing "
                f"{chunk.speaker1_file}"
            )

            failed = True

        if not Path(chunk.speaker2_file).exists():

            print(
                f"Missing "
                f"{chunk.speaker2_file}"
            )

            failed = True

    if failed:

        raise RuntimeError(
            "Cannot stitch because one or more chunks "
            "are missing or incomplete."
        )

    print("All chunk files verified.\n")


# ============================================================
# Crossfade
# ============================================================

def build_equal_power_fades(
    overlap_samples: int
):

    theta = np.linspace(
        0,
        np.pi / 2,
        overlap_samples,
        dtype=np.float32
    )

    fade_out = np.cos(theta)

    fade_in = np.sin(theta)

    return fade_out, fade_in


# ============================================================
# Audio
# ============================================================

def load_chunk(filename: str) -> np.ndarray:

    audio, sr = sf.read(filename)

    return audio.astype(np.float32)

# ============================================================
# Stitching
# ============================================================

def stitch_speaker(
    metadata: Metadata,
    speaker: int,
    output_file: Path,
):

    print(f"\nStitching Speaker {speaker}...")

    overlap_samples = int(
        metadata.overlap_seconds
        * metadata.sample_rate
    )

    fade_out, fade_in = build_equal_power_fades(
        overlap_samples
    )

    chunks = metadata.chunks

    pieces = []

    previous = None

    for chunk in chunks:

        filename = (
            chunk.speaker1_file
            if speaker == 1
            else chunk.speaker2_file
        )

        current = load_chunk(filename)

        if previous is None:

            pieces.append(
                current[:-overlap_samples]
            )

            previous = current

            continue

        crossfade = (
            previous[-overlap_samples:] * fade_out
            +
            current[:overlap_samples] * fade_in
        )

        pieces.append(crossfade)

        previous = current

        if chunk != chunks[-1]:

            pieces.append(
                current[
                    overlap_samples:
                    -overlap_samples
                ]
            )

    pieces.append(
        previous[overlap_samples:]
    )

    output = np.concatenate(pieces)

    print(
        f"Writing {output_file.name}..."
    )

    sf.write(
        output_file,
        output,
        metadata.sample_rate
    )

    print(
        f"Finished Speaker {speaker}."
    )

# ============================================================
# Main
# ============================================================

def main():

    metadata = Metadata(METADATA_FILE)

    metadata.load()

    verify_chunks(metadata)

    overlap_samples = int(
        metadata.overlap_seconds
        * metadata.sample_rate
    )

    fade_out, fade_in = build_equal_power_fades(
        overlap_samples
    )

    print("Metadata")

    print("-------------------------")

    print(f"Sample Rate : {metadata.sample_rate}")

    print(f"Chunk Size  : {metadata.chunk_seconds}s")

    print(f"Overlap     : {metadata.overlap_seconds}s")

    print(f"Chunks      : {len(metadata.chunks)}")

    print()

    print(
        f"Overlap Samples : {overlap_samples:,}"
    )

    print()

    print(
        f"Fade Length : {len(fade_in):,}"
    )

    print()

    stitch_speaker(
        metadata,
        speaker=1,
        output_file=OUTPUT_SPEAKER1
    )

    stitch_speaker(
        metadata,
        speaker=2,
        output_file=OUTPUT_SPEAKER2
    )

    print()

    print("Stitching complete.")


if __name__ == "__main__":

    main()