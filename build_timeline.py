from pathlib import Path
import json

import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt
from dataclasses import dataclass
from scipy.ndimage import binary_closing
from scipy.ndimage import binary_opening

INPUT_AUDIO = Path("output_20s/speaker2_full.wav")

OUTPUT_FOLDER = Path("timeline")

FRAME_MS = 25

SMOOTH_MS = 200

THRESHOLD_DB = -42

MIN_SPEECH_MS = 250

MIN_SILENCE_MS = 200

@dataclass
class SpeechSegment:

    id: int

    start: float

    end: float

    duration: float

    average_db: float

    peak_db: float

def frame_rms(audio, frame_size):

    frames = []

    for start in range(0, len(audio), frame_size):

        stop = min(start + frame_size, len(audio))

        chunk = audio[start:stop]

        rms = np.sqrt(
            np.mean(chunk ** 2)
        )

        frames.append(rms)

    return np.array(frames)

def smooth(signal, width):

    kernel = np.ones(width)

    kernel /= width

    return np.convolve(
        signal,
        kernel,
        mode="same"
    )

def build_speech_mask(energy_db, threshold_db):
    """
    True = speech
    False = silence
    """

    return energy_db > threshold_db

def remove_short_runs(mask, min_frames, value):
    """
    Removes runs of 'value' shorter than min_frames.
    """

    result = mask.copy()

    start = None

    for i in range(len(mask) + 1):

        current = mask[i] if i < len(mask) else not value

        if current == value:

            if start is None:
                start = i

        else:

            if start is not None:

                length = i - start

                if length < min_frames:
                    result[start:i] = ~value

                start = None

    return result

def clean_mask(mask):

    min_speech = int(
        MIN_SPEECH_MS / FRAME_MS
    )

    min_silence = int(
        MIN_SILENCE_MS / FRAME_MS
    )

    mask = remove_short_runs(
        mask,
        min_speech,
        True
    )

    mask = remove_short_runs(
        mask,
        min_silence,
        False
    )

    return mask

def plot_speech_mask(
    times,
    speech_mask,
    output_folder
):

    plt.figure(
        figsize=(18,2)
    )

    plt.fill_between(
        times,
        0,
        speech_mask.astype(int),
        step="post"
    )

    plt.ylim(
        -0.1,
        1.1
    )

    plt.xlabel("Seconds")

    plt.yticks(
        [0,1],
        ["Silence","Speech"]
    )

    plt.tight_layout()

    plt.savefig(
        output_folder /
        "speech_mask.png",
        dpi=200
    )

    plt.close()

def extract_segments(
    speech_mask,
    energy_db,
    frame_ms,
):

    segments = []

    start_frame = None

    segment_id = 0

    for i in range(len(speech_mask) + 1):

        speech = (
            speech_mask[i]
            if i < len(speech_mask)
            else False
        )

        if speech:

            if start_frame is None:
                start_frame = i

        else:

            if start_frame is not None:

                end_frame = i

                values = energy_db[
                    start_frame:end_frame
                ]

                start_sec = (
                    start_frame * frame_ms
                ) / 1000

                end_sec = (
                    end_frame * frame_ms
                ) / 1000

                segments.append(

                    SpeechSegment(

                        id=segment_id,

                        start=start_sec,

                        end=end_sec,

                        duration=end_sec-start_sec,

                        average_db=float(
                            np.mean(values)
                        ),

                        peak_db=float(
                            np.max(values)
                        )

                    )

                )

                segment_id += 1

                start_frame = None

    return segments

def save_timeline(
    segments,
    output_folder,
):

    data = []

    for s in segments:

        data.append({

            "id": s.id,

            "start": round(s.start,3),

            "end": round(s.end,3),

            "duration": round(s.duration,3),

            "average_db": round(
                s.average_db,
                2
            ),

            "peak_db": round(
                s.peak_db,
                2
            )

        })

    with open(

        output_folder /
        "timeline.json",

        "w",

        encoding="utf8"

    ) as f:

        json.dump(

            data,

            f,

            indent=4

        )

audio, sr = sf.read(INPUT_AUDIO)

if audio.ndim == 2:

    audio = np.mean(audio, axis=1)

frame_size = int(sr * FRAME_MS / 1000)

energy = frame_rms(
    audio,
    frame_size
)

energy_db = 20 * np.log10(
    energy + 1e-10
)

smooth_frames = max(
    1,
    int(SMOOTH_MS / FRAME_MS)
)

energy_db = smooth(
    energy_db,
    smooth_frames
)

speech_mask = build_speech_mask(
    energy_db,
    THRESHOLD_DB
)

speech_mask = clean_mask(
    speech_mask
)

speech_mask = binary_closing(
    speech_mask,
    iterations=40
)

speech_mask = binary_opening(
    speech_mask,
    iterations=10
)

OUTPUT_FOLDER.mkdir(
    exist_ok=True
)

times = np.arange(
    len(energy_db)
) * FRAME_MS / 1000

plot_speech_mask(
    times,
    speech_mask,
    OUTPUT_FOLDER
)

plt.figure(
    figsize=(18,4)
)

plt.plot(
    times,
    energy_db,
    linewidth=0.7
)

plt.axhline(
    THRESHOLD_DB,
    linestyle="--"
)

plt.xlabel("Seconds")

plt.ylabel("Energy (dB)")

plt.tight_layout()

plt.savefig(
    OUTPUT_FOLDER /
    "energy.png",
    dpi=200
)

plt.close()

segments = extract_segments(

    speech_mask,

    energy_db,

    FRAME_MS

)

save_timeline(

    segments,

    OUTPUT_FOLDER

)

print(f"Frames: {len(energy_db):,}")

print(f"Duration: {len(audio)/sr:.1f} seconds")

print()

print(f"Speech Segments : {len(segments):,}")

if segments:

    lengths = np.array(
        [s.duration for s in segments]
    )

    print(
        f"Average Length : "
        f"{np.mean(lengths):.2f}s"
    )

    print(
        f"Longest Segment: "
        f"{np.max(lengths):.2f}s"
    )

    print(
        f"Shortest Segment: "
        f"{np.min(lengths):.2f}s"
    )