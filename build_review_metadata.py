from pathlib import Path
import json
from itertools import combinations

import numpy as np
import soundfile as sf

REVIEW_FOLDER = Path("review")

RUN_NAMES = [

    "20s",

    "30s",

    "45s",

    "60s"

]

def correlation(a, b):

    a = a.astype(np.float64)

    b = b.astype(np.float64)

    a -= np.mean(a)

    b -= np.mean(b)

    denom = np.sqrt(
        np.sum(a*a) *
        np.sum(b*b)
    )

    if denom < 1e-12:

        return 0.0

    return float(
        np.sum(a*b) /
        denom
    )

def load_segment(folder):

    clips = {}

    sample_rate = None

    for run in RUN_NAMES:

        audio, sr = sf.read(
            folder /
            f"{run}.wav"
        )

        if sample_rate is None:

            sample_rate = sr

        elif sr != sample_rate:

            raise RuntimeError(
                "Sample rates differ."
            )

        if audio.ndim == 2:

            audio = np.mean(
                audio,
                axis=1
            )

        clips[run] = audio

    return clips

def compare_runs(clips):

    results = {}

    values = []

    for left, right in combinations(
        RUN_NAMES,
        2
    ):

        a = clips[left]

        b = clips[right]

        length = min(
            len(a),
            len(b)
        )

        value = correlation(

            a[:length],

            b[:length]

        )

        results[
            f"{left}_{right}"
        ] = value

        values.append(value)

    return results, values

def summarize(values):

    values = np.array(values)

    return {

        "min": float(np.min(values)),

        "max": float(np.max(values)),

        "average": float(np.mean(values)),

        "spread": float(
            np.max(values) -
            np.min(values)
        )

    }

def classify_priority(spread):

    if spread >= 0.08:

        return "High"

    if spread >= 0.04:

        return "Medium"

    return "Low"

def save_comparison(
    folder,
    metadata,
):

    with open(

        folder /
        "comparison.json",

        "w",

        encoding="utf8"

    ) as f:

        json.dump(

            metadata,

            f,

            indent=4

        )

def process_folder(folder):

    with open(

        folder /
        "metadata.json",

        "r",

        encoding="utf8"

    ) as f:

        segment = json.load(f)

    clips = load_segment(folder)

    correlations, values = compare_runs(clips)

    stats = summarize(values)

    output = {

        "segment": segment["id"],

        "start": segment["start"],

        "end": segment["end"],

        "duration": segment["duration"],

        "pairwise_correlation": correlations,

        "statistics": stats,

        "priority": classify_priority(
            stats["spread"]
        )

    }

    save_comparison(
        folder,
        output
    )

    return output

def main():

    folders = sorted(

        d

        for d in REVIEW_FOLDER.iterdir()

        if d.is_dir()

    )

    print(
        f"{len(folders)} review folders found."
    )

    counts = {

        "High": 0,

        "Medium": 0,

        "Low": 0

    }

    for i, folder in enumerate(folders):

        result = process_folder(folder)

        counts[
            result["priority"]
        ] += 1

        if (
            i % 25 == 0
            or
            i == len(folders)-1
        ):

            print(
                f"{i+1}/{len(folders)}"
            )

    print()

    print("Priority Summary")

    print(
        f"High   : {counts['High']}"
    )

    print(
        f"Medium : {counts['Medium']}"
    )

    print(
        f"Low    : {counts['Low']}"
    )

if __name__ == "__main__":

    main()