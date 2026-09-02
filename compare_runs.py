from pathlib import Path
from dataclasses import dataclass

import argparse
import soundfile as sf
import numpy as np
import matplotlib.pyplot as plt
import json
from scipy import signal


RUNS = {
    "20s": Path("output_20s"),
    "30s": Path("output_30s"),
    "45s": Path("output_45s"),
    "60s": Path("output_60s"),
}

OUTPUT_DIR = Path("comparison")

def parse_args():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--speaker",
        type=int,
        choices=[1, 2],
        default=2
    )

    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start time (SS, MM:SS or HH:MM:SS)"
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=10.0
    )

    return parser.parse_args()

def parse_timestamp(value: str) -> float:
    """
    Accepts:
        822
        13:42
        00:13:42
        00:13:42.500
    Returns seconds.
    """

    value = value.strip()

    # Plain seconds
    try:
        return float(value)
    except ValueError:
        pass

    parts = value.split(":")

    if len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])

        return minutes * 60 + seconds

    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])

        return (
            hours * 3600
            + minutes * 60
            + seconds
        )

    raise ValueError(
        f"Invalid timestamp: {value}"
    )

@dataclass
class RunAudio:

    name: str

    sample_rate: int

    audio: np.ndarray

def load_window(
    wav_file: Path,
    start_seconds: float,
    duration_seconds: float,
) -> tuple[np.ndarray, int]:

    audio, sr = sf.read(
        wav_file,
        dtype="float32"
    )

    start = int(start_seconds * sr)

    end = start + int(duration_seconds * sr)

    return audio[start:end], sr

def load_runs(
    speaker: int,
    start_seconds: float,
    duration_seconds: float,
):

    runs = []

    for name, folder in RUNS.items():

        wav = folder / f"speaker{speaker}_full.wav"

        audio, sr = load_window(
            wav,
            start_seconds,
            duration_seconds,
        )

        runs.append(
            RunAudio(
                name=name,
                sample_rate=sr,
                audio=audio,
            )
        )

    return runs

def verify_runs(runs):

    sr = runs[0].sample_rate

    samples = len(runs[0].audio)

    for run in runs:

        if run.sample_rate != sr:

            raise RuntimeError(
                "Sample rate mismatch."
            )

        if len(run.audio) != samples:

            raise RuntimeError(
                "Window lengths differ."
            )

    print()

    print("Loaded")

    for run in runs:

        print(
            f"{run.name:>4} "
            f"{len(run.audio):>8,d} samples"
        )

    print()

def export_windows(runs):

    OUTPUT_DIR.mkdir(
        exist_ok=True
    )

    for run in runs:

        sf.write(
            OUTPUT_DIR /
            f"{run.name}.wav",
            run.audio,
            run.sample_rate
        )

def get_output_folder(start_seconds: float):

    hours = int(start_seconds // 3600)

    minutes = int((start_seconds % 3600) // 60)

    seconds = start_seconds % 60

    folder = (
        OUTPUT_DIR /
        f"{hours:02d}-{minutes:02d}-{seconds:06.3f}"
    )

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    return folder

def plot_waveforms(
    runs,
    output_folder,
):

    fig, axes = plt.subplots(
        len(runs),
        1,
        figsize=(14, 8),
        sharex=True,
    )

    for ax, run in zip(axes, runs):

        ax.plot(
            run.audio,
            linewidth=0.5,
        )

        ax.set_ylabel(run.name)

    axes[-1].set_xlabel("Samples")

    plt.tight_layout()

    plt.savefig(
        output_folder /
        "waveforms.png",
        dpi=200,
    )

    plt.close()

def compute_correlations(runs):

    matrix = {}

    for run1 in runs:

        matrix[run1.name] = {}

        for run2 in runs:

            corr = np.corrcoef(
                run1.audio,
                run2.audio,
            )[0, 1]

            matrix[run1.name][run2.name] = float(corr)

    return matrix

def save_json(
    filename,
    data,
):

    with open(
        filename,
        "w",
        encoding="utf8",
    ) as f:

        json.dump(
            data,
            f,
            indent=4,
        )

def disagreement_curve(
    runs,
    window_ms=100,
):

    sr = runs[0].sample_rate

    window = int(
        sr * window_ms / 1000
    )

    values = []

    for start in range(
        0,
        len(runs[0].audio) - window,
        window,
    ):

        stop = start + window

        total = 0.0

        count = 0

        for i in range(len(runs)):

            for j in range(i + 1, len(runs)):

                diff = (
                    runs[i].audio[start:stop]
                    -
                    runs[j].audio[start:stop]
                )

                rms = np.sqrt(
                    np.mean(diff ** 2)
                )

                total += rms

                count += 1

        values.append(
            total / count
        )

    return np.array(values)

def plot_disagreement(
    curve,
    output_folder,
):

    plt.figure(
        figsize=(14, 3)
    )

    plt.plot(curve)

    plt.ylabel("Average RMS Difference")

    plt.xlabel("100 ms Window")

    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        output_folder /
        "disagreement.png",
        dpi=200,
    )

    plt.close()

def compute_spectrogram(audio, sample_rate):

    frequencies, times, spectrum = signal.spectrogram(
        audio,
        fs=sample_rate,
        window="hann",
        nperseg=1024,
        noverlap=768,
        scaling="spectrum",
        mode="magnitude"
    )

    spectrum = 20 * np.log10(
        spectrum + 1e-10
    )

    return frequencies, times, spectrum

def plot_spectrograms(
    runs,
    output_folder,
):

    fig, axes = plt.subplots(
        len(runs),
        1,
        figsize=(15, 10),
        sharex=True,
        sharey=True,
    )

    for ax, run in zip(axes, runs):

        f, t, s = compute_spectrogram(
            run.audio,
            run.sample_rate,
        )

        image = ax.imshow(
            s,
            origin="lower",
            aspect="auto",
            extent=[
                t[0],
                t[-1],
                f[0],
                f[-1],
            ],
            vmin=-90,
            vmax=-20,
        )

        ax.set_ylabel(run.name)

    axes[-1].set_xlabel(
        "Time (seconds)"
    )

    fig.colorbar(
        image,
        ax=axes,
        label="dB"
    )

    plt.tight_layout()

    plt.savefig(
        output_folder /
        "spectrograms.png",
        dpi=250,
    )

    plt.close()

def plot_difference(
    runs,
    output_folder,
):

    reference = compute_spectrogram(
        runs[0].audio,
        runs[0].sample_rate,
    )

    f = reference[0]
    t = reference[1]
    ref = reference[2]

    fig, axes = plt.subplots(
        len(runs) - 1,
        1,
        figsize=(15, 8),
        sharex=True,
        sharey=True,
    )

    for ax, run in zip(
        axes,
        runs[1:]
    ):

        _, _, current = compute_spectrogram(
            run.audio,
            run.sample_rate,
        )

        diff = np.abs(
            ref - current
        )

        image = ax.imshow(
            diff,
            origin="lower",
            aspect="auto",
            extent=[
                t[0],
                t[-1],
                f[0],
                f[-1],
            ],
            vmin=0,
            vmax=30,
        )

        ax.set_ylabel(
            f"{run.name}-20s"
        )

    axes[-1].set_xlabel(
        "Time (seconds)"
    )

    fig.colorbar(
        image,
        ax=axes,
        label="Difference (dB)"
    )

    plt.tight_layout()

    plt.savefig(
        output_folder /
        "difference.png",
        dpi=250,
    )

    plt.close()

def main():

    args = parse_args()

    start_seconds = parse_timestamp(args.start)

    runs = load_runs(
        args.speaker,
        start_seconds,
        args.duration,
    )

    verify_runs(runs)

    export_windows(runs)

    output_folder = get_output_folder(
        start_seconds
    )

    plot_waveforms(
        runs,
        output_folder,
    )

    corr = compute_correlations(
        runs
    )

    save_json(
        output_folder /
        "correlation.json",
        corr,
    )

    curve = disagreement_curve(
        runs
    )

    plot_disagreement(
        curve,
        output_folder,
    )
    
    plot_spectrograms(
        runs,
        output_folder,
    )

    plot_difference(
        runs,
        output_folder,
    )
    print()

    print("Analysis complete.")

if __name__ == "__main__":

    main()