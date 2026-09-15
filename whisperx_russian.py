import argparse
import json
from pathlib import Path

import whisperx


DEFAULT_AUDIO = r"C:/Users/jshar/Desktop/From Youtube/audio.wav"
DEFAULT_OUTPUT = "whisperx_russian.json"

INITIAL_PROMPT = (
    "Это телепередача Junkyard Mega Wars - At the Movies об автомобилях, "
    "механике, двигателях, машинах и инженерных соревнованиях. "
    "Используются технические термины и названия деталей автомобилей."
)


def format_srt_time(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds_part, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d},{millis:03d}"


def write_srt(segments: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        subtitle_number = 1
        for segment in segments:
            text = str(segment.get("text", "")).strip()
            start = segment.get("start")
            end = segment.get("end")
            if not text or start is None or end is None:
                continue

            handle.write(f"{subtitle_number}\n")
            handle.write(
                f"{format_srt_time(float(start))} --> "
                f"{format_srt_time(float(end))}\n"
            )
            handle.write(f"{text}\n\n")
            subtitle_number += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe Russian audio with WhisperX and forced alignment."
    )
    parser.add_argument(
        "--audio",
        default=DEFAULT_AUDIO,
        help=f"Input audio file (default: {DEFAULT_AUDIO})",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--model",
        default="large-v3",
        help="WhisperX/faster-whisper model name (default: large-v3)",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="Processing device (default: auto)",
    )
    parser.add_argument(
        "--compute-type",
        default=None,
        help="WhisperX compute type; defaults to float16 on CUDA and int8 on CPU",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="WhisperX batch size (default: 4)",
    )
    parser.add_argument(
        "--start",
        type=float,
        default=0.0,
        help="Start time in seconds; useful for short tests",
    )
    parser.add_argument(
        "--end",
        type=float,
        default=None,
        help="End time in seconds; useful for short tests",
    )
    parser.add_argument(
        "--no-align",
        action="store_true",
        help="Skip forced alignment (not recommended for this experiment)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    audio_path = Path(args.audio)
    output_path = Path(args.output)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if args.start < 0:
        raise ValueError("--start cannot be negative")
    if args.end is not None and args.end <= args.start:
        raise ValueError("--end must be greater than --start")

    if args.device == "auto":
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device

    compute_type = args.compute_type
    if compute_type is None:
        compute_type = "float16" if device == "cuda" else "int8"

    print(f"Audio: {audio_path}")
    print(f"Device: {device}")
    print(f"Compute type: {compute_type}")
    print(f"Model: {args.model}")

    print("Loading audio")
    audio = whisperx.load_audio(str(audio_path))
    sample_rate = 16_000

    start_sample = int(args.start * sample_rate)
    end_sample = (
        int(args.end * sample_rate)
        if args.end is not None
        else len(audio)
    )
    if start_sample >= len(audio):
        raise ValueError("--start is beyond the end of the audio")
    end_sample = min(end_sample, len(audio))
    audio_segment = audio[start_sample:end_sample]

    actual_start = start_sample / sample_rate
    actual_end = end_sample / sample_rate
    print(f"Transcribing {actual_start:.3f}s -> {actual_end:.3f}s")

    print("Loading WhisperX model")
    model = whisperx.load_model(
        args.model,
        device=device,
        compute_type=compute_type,
        language="ru",
    )

    print("Transcribing Russian")
    result = model.transcribe(
        audio_segment,
        batch_size=args.batch_size,
        language="ru",
        task="transcribe",
        initial_prompt=INITIAL_PROMPT,
        condition_on_previous_text=False,
    )

    # The model saw a sliced audio buffer. Put segment timestamps back into
    # the original episode timeline before writing any output.
    for segment in result.get("segments", []):
        segment["start"] = float(segment["start"]) + actual_start
        segment["end"] = float(segment["end"]) + actual_start
        for word in segment.get("words", []):
            if word.get("start") is not None:
                word["start"] = float(word["start"]) + actual_start
            if word.get("end") is not None:
                word["end"] = float(word["end"]) + actual_start

    if not args.no_align and result.get("segments"):
        print("Loading Russian forced-alignment model")
        align_model, align_metadata = whisperx.load_align_model(
            language_code="ru",
            device=device,
        )

        # Alignment operates on the sliced audio, so temporarily move the
        # timestamps back to the slice's local timeline.
        local_segments = []
        for segment in result["segments"]:
            local_segment = dict(segment)
            local_segment["start"] = float(segment["start"]) - actual_start
            local_segment["end"] = float(segment["end"]) - actual_start
            local_segments.append(local_segment)

        print("Forced-aligning Russian words")
        aligned_segments = whisperx.align(
            local_segments,
            align_model,
            align_metadata,
            audio_segment,
            device,
            return_char_alignments=False,
        )

        for segment in aligned_segments["segments"]:
            segment["start"] = float(segment["start"]) + actual_start
            segment["end"] = float(segment["end"]) + actual_start
            for word in segment.get("words", []):
                if word.get("start") is not None:
                    word["start"] = float(word["start"]) + actual_start
                if word.get("end") is not None:
                    word["end"] = float(word["end"]) + actual_start

        result = aligned_segments

    result["audio"] = str(audio_path)
    result["language"] = "ru"
    result["model"] = args.model
    result["device"] = device
    result["compute_type"] = compute_type
    result["forced_alignment"] = not args.no_align
    result["source_start"] = actual_start
    result["source_end"] = actual_end

    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing JSON: {output_path}")
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)

    srt_path = output_path.with_suffix(".srt")
    print(f"Writing SRT: {srt_path}")
    write_srt(result.get("segments", []), srt_path)

    print("WhisperX Russian transcription complete!")
    print(f"Segments: {len(result.get('segments', []))}")


if __name__ == "__main__":
    main()
