from pathlib import Path
import json

import numpy as np
import soundfile as sf

PADDING_MS = 250

TIMELINE_FILE = Path(
    "timeline/timeline.json"
)

OUTPUT_FOLDER = Path(
    "review"
)

RUNS = {

    "20s": Path(
        "output_20s/speaker2_full.wav"
    ),

    "30s": Path(
        "output_30s/speaker2_full.wav"
    ),

    "45s": Path(
        "output_45s/speaker2_full.wav"
    ),

    "60s": Path(
        "output_60s/speaker2_full.wav"
    )

}

def load_timeline():

    with open(
        TIMELINE_FILE,
        "r",
        encoding="utf8"
    ) as f:

        return json.load(f)


def load_runs():

    audio = {}

    sample_rate = None

    for name, file in RUNS.items():

        print(f"Loading {name}...")

        samples, sr = sf.read(file)

        if sample_rate is None:

            sample_rate = sr

        elif sr != sample_rate:

            raise RuntimeError(
                "Sample rates differ."
            )

        audio[name] = samples

    return audio, sample_rate

def extract_clip(
    audio,
    sample_rate,
    start_time,
    end_time,
):

    padding = int(
        sample_rate *
        PADDING_MS /
        1000
    )

    start = max(
        0,
        int(start_time * sample_rate) - padding
    )

    end = min(
        len(audio),
        int(end_time * sample_rate) + padding
    )

    return audio[start:end]

def save_metadata(
    folder,
    segment,
):

    with open(
        folder / "metadata.json",
        "w",
        encoding="utf8"
    ) as f:

        json.dump(
            segment,
            f,
            indent=4
        )

def extract_segments(
    timeline,
    audio,
    sample_rate,
):

    OUTPUT_FOLDER.mkdir(
        exist_ok=True
    )

    total = len(timeline)

    for i, segment in enumerate(timeline):

        folder = (
            OUTPUT_FOLDER /
            f"{segment['id']:04d}"
        )

        folder.mkdir(
            exist_ok=True
        )

        save_metadata(
            folder,
            segment
        )

        for name, samples in audio.items():

            clip = extract_clip(

                samples,

                sample_rate,

                segment["start"],

                segment["end"]

            )

            sf.write(

                folder /
                f"{name}.wav",

                clip,

                sample_rate

            )

        if (
            i % 25 == 0
            or
            i == total - 1
        ):

            print(
                f"{i+1}/{total}"
            )

def main():

    print(
        "Loading timeline..."
    )

    timeline = load_timeline()

    audio, sr = load_runs()

    print()

    print(
        f"Timeline segments : {len(timeline)}"
    )

    print(
        f"Sample rate       : {sr}"
    )

    print()

    print()

    print(
        f"Extracting {len(timeline)} segments..."
    )

    extract_segments(

        timeline,

        audio,

        sr

    )

    print()

    print(
        "Extraction complete."
    )

if __name__ == "__main__":
    main()