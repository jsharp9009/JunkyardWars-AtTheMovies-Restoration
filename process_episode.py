"""
Junkyard Wars Audio Separation
Version 1

Part 1
-------

✓ Configuration
✓ Audio loading
✓ Metadata
✓ Chunk planning
✓ Resume support

No AI processing yet.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
from clearvoice import ClearVoice
from datetime import timedelta
import json
import math
import time
import argparse

import librosa
import numpy as np
import soundfile as sf


# ============================================================
# Configuration
# ============================================================

INPUT_FILE = Path("C:/Users/jshar/Desktop/From Youtube/audio.wav")

OUTPUT_DIR = Path("output")

METADATA_FILE = OUTPUT_DIR / "metadata.json"

SPEAKER1_DIR = OUTPUT_DIR / "speaker1_chunks"

SPEAKER2_DIR = OUTPUT_DIR / "speaker2_chunks"

TARGET_SAMPLE_RATE = 16000

CHUNK_SECONDS = 45

OVERLAP_SECONDS = 1


# ============================================================
# Data Classes
# ============================================================

@dataclass
class ChunkInfo:

    index: int

    start_sample: int

    end_sample: int

    start_seconds: float

    end_seconds: float

    status: str = "pending"

    processing_time: float | None = None

    speaker1_file: str | None = None

    speaker2_file: str | None = None
    error: str | None = None


# ============================================================
# Metadata
# ============================================================

class MetadataManager:

    def __init__(self, filename: Path):

        self.filename = filename

        self.data = {}

    def exists(self):

        return self.filename.exists()

    def load(self):

        with open(self.filename, "r", encoding="utf8") as f:

            self.data = json.load(f)

    def create(self, chunks):

        self.data = {

            "version": 1,

            "created": datetime.now().isoformat(),

            "input_file": str(INPUT_FILE),

            "sample_rate": TARGET_SAMPLE_RATE,

            "chunk_seconds": CHUNK_SECONDS,

            "overlap_seconds": OVERLAP_SECONDS,

            "chunks": [

                asdict(c)

                for c in chunks

            ]

        }

    def save(self):

        with open(self.filename, "w", encoding="utf8") as f:

            json.dump(
                self.data,
                f,
                indent=4
            )

    def completed_chunks(self):

        complete = set()

        for chunk in self.data["chunks"]:

            if chunk["status"] == "complete":

                complete.add(chunk["index"])

        return complete
    def update_chunk(
        self,
        chunk: ChunkInfo
    ):

        for existing in self.data["chunks"]:

            if existing["index"] == chunk.index:

                existing.update(asdict(chunk))

                return

    def verify_completed_chunk(
        self,
        index: int,
    ):

        chunk = self.data["chunks"][index]

        speaker1 = Path(chunk["speaker1_file"])

        speaker2 = Path(chunk["speaker2_file"])

        if not speaker1.exists() or not speaker2.exists():

            print(
                f"Chunk {index:04d} marked complete "
                "but output files are missing."
            )

            chunk["status"] = "pending"

            chunk["speaker1_file"] = None

            chunk["speaker2_file"] = None

            chunk["processing_time"] = None

            chunk["error"] = None

            self.save()

            return False

        return True

class MossFormerSeparator:
    """
    Thin wrapper around ClearVoice.

    The rest of the program should never call ClearVoice directly.
    """

    def __init__(self):

        print("Loading MossFormer2...")

        self.model = ClearVoice(
            task="speech_separation",
            model_names=["MossFormer2_SS_16K"]
        )

        print("Model loaded.\n")

    def process(
        self,
        audio: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:

        # ClearVoice expects [batch, samples]

        audio = np.reshape(audio, (1, len(audio)))

        audio = audio.astype(np.float32)

        output = self.model(audio, False)

        speaker1 = output[0, 0, :]

        speaker2 = output[1, 0, :]

        return speaker1, speaker2

# ============================================================
# Utility
# ============================================================

def ensure_directories():

    OUTPUT_DIR.mkdir(exist_ok=True)

    SPEAKER1_DIR.mkdir(exist_ok=True)

    SPEAKER2_DIR.mkdir(exist_ok=True)


# ============================================================
# Audio
# ============================================================

def load_audio():

    print("Loading audio...")

    audio, sr = sf.read(INPUT_FILE)

    print(f"Original sample rate : {sr}")

    print(f"Original shape       : {audio.shape}")

    if audio.ndim == 2:

        print("Converting stereo to mono...")

        audio = np.mean(audio, axis=1)

    if sr != TARGET_SAMPLE_RATE:

        print("Resampling...")

        audio = librosa.resample(
            audio,
            orig_sr=sr,
            target_sr=TARGET_SAMPLE_RATE
        )

        sr = TARGET_SAMPLE_RATE

    audio = audio.astype(np.float32)

    print()

    print(f"Final length : {len(audio):,} samples")

    print(f"Duration     : {len(audio)/sr:.1f} sec")

    return audio


# ============================================================
# Chunk Planner
# ============================================================

def build_chunks(total_samples):

    chunk_size = CHUNK_SECONDS * TARGET_SAMPLE_RATE

    overlap = OVERLAP_SECONDS * TARGET_SAMPLE_RATE

    step = chunk_size - overlap

    chunks = []

    index = 0

    start = 0

    while start < total_samples:

        end = min(start + chunk_size, total_samples)

        chunks.append(

            ChunkInfo(

                index=index,

                start_sample=start,

                end_sample=end,

                start_seconds=start / TARGET_SAMPLE_RATE,

                end_seconds=end / TARGET_SAMPLE_RATE

            )

        )

        start += step

        index += 1

    return chunks


# ============================================================
# Validation
# ============================================================

# ============================================================
# Validation
# ============================================================

def validate_chunk(
    input_chunk: np.ndarray,
    speaker1: np.ndarray,
    speaker2: np.ndarray,
):

    expected = len(input_chunk)

    if len(speaker1) != expected:
        raise RuntimeError("Speaker 1 length mismatch.")

    if len(speaker2) != expected:
        raise RuntimeError("Speaker 2 length mismatch.")

    if np.isnan(speaker1).any():
        raise RuntimeError("Speaker 1 contains NaNs.")

    if np.isnan(speaker2).any():
        raise RuntimeError("Speaker 2 contains NaNs.")

    if np.isinf(speaker1).any():
        raise RuntimeError("Speaker 1 contains Infs.")

    if np.isinf(speaker2).any():
        raise RuntimeError("Speaker 2 contains Infs.")

    # Reject silent output

    if np.max(np.abs(speaker1)) < 1e-6:
        raise RuntimeError("Speaker 1 output is silent.")

    if np.max(np.abs(speaker2)) < 1e-6:
        raise RuntimeError("Speaker 2 output is silent.")

# ============================================================
# Output
# ============================================================

def save_chunk(
    chunk: ChunkInfo,
    speaker1: np.ndarray,
    speaker2: np.ndarray
):

    speaker1_filename = SPEAKER1_DIR / f"{chunk.index:04d}.wav"

    speaker2_filename = SPEAKER2_DIR / f"{chunk.index:04d}.wav"

    sf.write(
        speaker1_filename,
        speaker1,
        TARGET_SAMPLE_RATE
    )

    sf.write(
        speaker2_filename,
        speaker2,
        TARGET_SAMPLE_RATE
    )

    chunk.speaker1_file = str(speaker1_filename)

    chunk.speaker2_file = str(speaker2_filename)

# ============================================================
# Progress
# ============================================================

def format_time(seconds: float) -> str:
    """
    Convert seconds into a human-readable duration.
    """

    seconds = int(seconds)

    return str(timedelta(seconds=seconds))

# ============================================================
# Processing
# ============================================================

def process_chunks(
    audio: np.ndarray,
    chunks: list[ChunkInfo],
    metadata: MetadataManager,
    separator: MossFormerSeparator,
     chunk_filter: int | None = None,
):

    completed = set()

    for index in metadata.completed_chunks():

        if metadata.verify_completed_chunk(index):

            completed.add(index)

    if chunk_filter is not None:

        print()

        print(f"Single Chunk Mode")

        print(f"Processing chunk {chunk_filter:04d}")

        print()

    processed_count = len(completed)

    total_chunks = len(chunks)

    overall_start = time.perf_counter()

    for chunk in chunks:
        # If a specific chunk was requested,
        # ignore all others.

        if chunk_filter is not None:

            if chunk.index != chunk_filter:

                continue

        # Normal resume mode skips completed chunks.
        # Single-chunk mode always reprocesses.

        if chunk_filter is None:

            if chunk.index in completed:

                print(f"Skipping chunk {chunk.index:04d}")

                continue

        print(
            f"\nChunk {chunk.index:04d} "
            f"({chunk.start_seconds:.1f}s - "
            f"{chunk.end_seconds:.1f}s)"
        )

        try:

            start = time.perf_counter()

            input_chunk = np.copy(
                audio[
                    chunk.start_sample:
                    chunk.end_sample
                ]
            )

            speaker1, speaker2 = separator.process(
                input_chunk
            )

            validate_chunk(
                input_chunk,
                speaker1,
                speaker2
            )

            save_chunk(
                chunk,
                speaker1,
                speaker2
            )

            chunk.processing_time = (
                time.perf_counter() - start
            )

            chunk.status = "complete"

            chunk.error = None

            metadata.update_chunk(chunk)

            metadata.save()

            processed_count += 1

            elapsed_total = (
                time.perf_counter()
                - overall_start
            )

            average = (
                elapsed_total
                / processed_count
            )

            remaining = (
                total_chunks
                - processed_count
            )

            eta = average * remaining

            print(f"✓ {chunk.processing_time:.2f}s")

            print(
                f"Progress : "
                f"{processed_count}/{total_chunks}"
            )

            print(
                f"Average  : "
                f"{average:.2f}s per chunk"
            )

            print(
                f"ETA      : "
                f"{format_time(eta)}"
            )

        except Exception as e:

            chunk.status = "failed"

            chunk.error = str(e)

            metadata.update_chunk(chunk)

            metadata.save()

            print("\nFAILED")

            print(e)

    elapsed = (
        time.perf_counter()
        - overall_start
    )

    print()

    print("=" * 60)

    print("Processing Complete")

    print("=" * 60)

    print(
        f"Chunks processed : "
        f"{processed_count}"
    )

    print(
        f"Total chunks     : "
        f"{total_chunks}"
    )

    print(
        f"Elapsed          : "
        f"{format_time(elapsed)}"
    )

    print()

    print("Speaker chunk files written to:")

    print(f"  {SPEAKER1_DIR}")

    print(f"  {SPEAKER2_DIR}")

# ============================================================
# Command Line
# ============================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description="Process Junkyard Wars episode with MossFormer."
    )

    parser.add_argument(
        "--chunk",
        type=int,
        help="Process only a single chunk index."
    )

    return parser.parse_args()

# ============================================================
# Main
# ============================================================

def main():

    args = parse_arguments()
    ensure_directories()

    audio = load_audio()

    print()

    print("Planning chunks...")

    chunks = build_chunks(len(audio))

    print(f"Created {len(chunks)} chunks.")

    metadata = MetadataManager(METADATA_FILE)

    if metadata.exists():

        print()

        print("Loading existing metadata...")

        metadata.load()

        print(
            f"{len(metadata.completed_chunks())} "
            "completed chunks found."
        )

    else:

        print()

        print("Creating metadata...")

        metadata.create(chunks)

        metadata.save()

        print("metadata.json written.")

    separator = MossFormerSeparator()

    process_chunks(
        audio,
        chunks,
        metadata,
        separator,
        chunk_filter=args.chunk,
    )

    # ============================================================
# Command Line
# ============================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description="Process Junkyard Wars episode with MossFormer."
    )

    parser.add_argument(
        "--chunk",
        type=int,
        help="Process only a single chunk index."
    )

    return parser.parse_args()

if __name__ == "__main__":

    main()