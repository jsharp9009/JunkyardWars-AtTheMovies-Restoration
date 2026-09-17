"""Run Auto-AVSR visual speech recognition against a video clip.

This is intentionally a small test runner rather than a full-episode pipeline.
Auto-AVSR is an external dependency/repository. Install it separately and point
--auto-avsr-dir at that checkout.

The first phase of lip-reading is evidence gathering. This script therefore
keeps the raw Auto-AVSR stdout and writes a small JSON record rather than
pretending the transcript has reliable word-level timestamps.

Example:
    python lip_reading_auto_avsr.py \
        --video "C:/Junkyard Restoration/source/episode.mp4" \
        --auto-avsr-dir "C:/AI/auto_avsr" \
        --checkpoint "C:/AI/auto_avsr/pretrained/vsr_trlrwlrs2lrs3vox2avsp_base.pth" \
        --start 600 \
        --duration 60

Auto-AVSR's published demo accepts video/audio input and a pretrained model;
its visual-only model is the VSR/lip-reading path. See the project README for
installation and model-zoo details.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_CHECKPOINT_NAME = "vsr_trlrwlrs2lrs3vox2avsp_base.pth"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Auto-AVSR visual-only speech recognition on a video clip."
    )
    parser.add_argument("--video", required=True, help="Source episode video")
    parser.add_argument(
        "--auto-avsr-dir",
        required=True,
        help="Path to the Auto-AVSR checkout containing demo.py",
    )
    parser.add_argument(
        "--checkpoint",
        required=True,
        help="Path to the Auto-AVSR visual-only pretrained checkpoint",
    )
    parser.add_argument(
        "--start",
        type=float,
        default=0.0,
        help="Start time in seconds in the source video (default: 0)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="Duration of the test clip in seconds (default: 60)",
    )
    parser.add_argument(
        "--output",
        default="auto_avsr_lip_reading.json",
        help="JSON output path (default: auto_avsr_lip_reading.json)",
    )
    parser.add_argument(
        "--detector",
        choices=("retinaface", "mediapipe"),
        default="mediapipe",
        help=(
            "Face detector to use. mediapipe is the default because it avoids "
            "the hard-coded CUDA device in the older RetinaFace demo."
        ),
    )
    parser.add_argument(
        "--keep-clip",
        action="store_true",
        help="Keep the temporary test clip next to the JSON output",
    )
    return parser.parse_args()


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise SystemExit(f"{label} does not exist: {path}")


def make_clip(source: Path, destination: Path, start: float, duration: float) -> None:
    if start < 0:
        raise SystemExit("--start must be >= 0")
    if duration <= 0:
        raise SystemExit("--duration must be > 0")

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(start),
        "-i",
        str(source),
        "-t",
        str(duration),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-y",
        str(destination),
    ]

    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise SystemExit(
            "ffmpeg was not found on PATH. Install ffmpeg before running this script."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"ffmpeg failed with exit code {exc.returncode}") from exc


def run_auto_avsr(
    auto_avsr_dir: Path,
    checkpoint: Path,
    clip: Path,
    detector: str,
) -> tuple[str, str, int]:
    demo = auto_avsr_dir / "demo.py"
    require_file(demo, "Auto-AVSR demo.py")

    command = [
        sys.executable,
        str(demo),
        "data.modality=video",
        f"pretrained_model_path={checkpoint.resolve()}",
        f"file_path={clip.resolve()}",
    ]

    # The stock demo hard-codes RetinaFace to cuda:0. For this reason we use
    # MediaPipe by default and patch the detector choice through a tiny
    # environment variable consumed below when supported by our wrapper.
    # The older demo itself does not expose detector= as a Hydra argument.
    env = dict(**__import__("os").environ)
    env["AUTO_AVSR_DETECTOR"] = detector

    completed = subprocess.run(
        command,
        cwd=auto_avsr_dir,
        text=True,
        capture_output=True,
        env=env,
    )

    return completed.stdout, completed.stderr, completed.returncode


def extract_transcript(stdout: str) -> str:
    matches = re.findall(r"transcript:\s*(.+)", stdout)
    if not matches:
        return ""
    return matches[-1].strip()


def main() -> None:
    args = parse_args()

    source = Path(args.video).expanduser().resolve()
    auto_avsr_dir = Path(args.auto_avsr_dir).expanduser().resolve()
    checkpoint = Path(args.checkpoint).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()

    require_file(source, "Video")
    require_file(checkpoint, "Checkpoint")
    if not auto_avsr_dir.is_dir():
        raise SystemExit(f"Auto-AVSR directory does not exist: {auto_avsr_dir}")

    output.parent.mkdir(parents=True, exist_ok=True)

    clip_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="auto_avsr_",
            suffix=".mp4",
            dir=output.parent,
            delete=False,
        ) as temp:
            clip_path = Path(temp.name)

        print(f"Creating test clip: {clip_path}")
        make_clip(source, clip_path, args.start, args.duration)

        print("Running Auto-AVSR visual speech recognition...")
        stdout, stderr, returncode = run_auto_avsr(
            auto_avsr_dir,
            checkpoint,
            clip_path,
            args.detector,
        )

        result = {
            "tool": "Auto-AVSR",
            "mode": "visual",
            "source_video": str(source),
            "source_start": args.start,
            "source_duration_requested": args.duration,
            "test_clip": str(clip_path) if args.keep_clip else None,
            "checkpoint": str(checkpoint),
            "detector": args.detector,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "return_code": returncode,
            "transcript": extract_transcript(stdout),
            "stdout": stdout,
            "stderr": stderr,
            "timestamp_note": (
                "Auto-AVSR demo output is retained as raw evidence. This wrapper "
                "does not invent word-level timestamps."
            ),
        }

        output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"Wrote: {output}")
        if returncode != 0:
            raise SystemExit(returncode)
        print(f"Transcript: {result['transcript']}")

    finally:
        if clip_path is not None and clip_path.exists() and not args.keep_clip:
            clip_path.unlink()


if __name__ == "__main__":
    main()
