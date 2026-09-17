"""Run Auto-AVSR v1.0.0 visual speech recognition against a video clip.

This is intentionally a small test runner rather than a full-episode pipeline.
Auto-AVSR is an external dependency/repository. Use the official v1.0.0
checkout, which contains demo.py and configs/config.yaml.

The first phase of lip-reading is evidence gathering. This script therefore
keeps the raw Auto-AVSR stdout and writes a small JSON record rather than
pretending the transcript has reliable word-level timestamps.

The v1.0.0 demo defaults to the RetinaFace detector, whose implementation
requires CUDA. This runner temporarily patches the demo's final
InferencePipeline call so MediaPipe is selected instead. The external
Auto-AVSR checkout itself is never modified.

Example:
    python lip_reading_auto_avsr.py \
        --video "C:/Junkyard Restoration/source/episode.mp4" \
        --auto-avsr-dir "C:/AI/auto_avsr_v1" \
        --checkpoint "C:/AI/auto_avsr_v1/vsr_trlrwlrs2lrs3vox2avsp_base.pth" \
        --start 600 \
        --duration 20

Auto-AVSR v1.0.0's official demo supports video-only inference. The model
zoo's strongest visual-only LRS3 checkpoint is
vsr_trlrwlrs2lrs3vox2avsp_base.pth.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Auto-AVSR v1.0.0 visual-only speech recognition on a video clip."
    )
    parser.add_argument("--video", required=True, help="Source episode video")
    parser.add_argument(
        "--auto-avsr-dir",
        required=True,
        help="Path to the Auto-AVSR v1.0.0 checkout containing demo.py and configs/",
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
        default=20.0,
        help="Duration of the test clip in seconds (default: 20)",
    )
    parser.add_argument(
        "--output",
        default="auto_avsr_lip_reading.json",
        help="JSON output path (default: auto_avsr_lip_reading.json)",
    )
    parser.add_argument(
        "--detector",
        choices=("mediapipe",),
        default="mediapipe",
        help="Face detector to use; CPU testing uses MediaPipe (default: mediapipe)",
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


def require_auto_avsr_v1(auto_avsr_dir: Path) -> None:
    if not auto_avsr_dir.is_dir():
        raise SystemExit(f"Auto-AVSR directory does not exist: {auto_avsr_dir}")

    require_file(auto_avsr_dir / "demo.py", "Auto-AVSR v1.0.0 demo.py")
    require_file(
        auto_avsr_dir / "configs" / "config.yaml",
        "Auto-AVSR v1.0.0 configs/config.yaml",
    )


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
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-an",
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
    """Run the official v1.0.0 demo without modifying its checkout.

    Auto-AVSR v1.0.0's demo.py constructs InferencePipeline(cfg) without
    exposing the detector as a Hydra option. Its default detector is RetinaFace,
    which requires CUDA. We make a temporary copy and inject the detector
    argument so CPU + MediaPipe can be selected.
    """
    demo = auto_avsr_dir / "demo.py"
    require_file(demo, "Auto-AVSR v1.0.0 demo.py")

    source = demo.read_text(encoding="utf-8")
    original = "pipeline = InferencePipeline(cfg)"
    replacement = (
        "pipeline = InferencePipeline("
        "cfg, detector=os.environ.get(\"AUTO_AVSR_DETECTOR\", \"retinaface\")"
        ")"
    )

    if original not in source:
        raise SystemExit(
            "The Auto-AVSR v1.0.0 demo.py layout is different from the version "
            "this runner supports. Inspect demo.py before continuing."
        )

    patched_source = source.replace(original, replacement, 1)
    patched_demo = auto_avsr_dir / ".junkyard_auto_avsr_demo.py"
    patched_demo.write_text(patched_source, encoding="utf-8")

    command = [
        sys.executable,
        str(patched_demo),
        "data.modality=video",
        f"pretrained_model_path={checkpoint.resolve()}",
        f"file_path={clip.resolve()}",
    ]

    env = os.environ.copy()
    env["AUTO_AVSR_DETECTOR"] = detector

    try:
        completed = subprocess.run(
            command,
            cwd=auto_avsr_dir,
            text=True,
            capture_output=True,
            env=env,
        )
    finally:
        patched_demo.unlink(missing_ok=True)

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
    require_auto_avsr_v1(auto_avsr_dir)

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

        print(f"Creating visual-only test clip: {clip_path}")
        make_clip(source, clip_path, args.start, args.duration)

        print("Running Auto-AVSR v1.0.0 visual speech recognition on CPU...")
        stdout, stderr, returncode = run_auto_avsr(
            auto_avsr_dir,
            checkpoint,
            clip_path,
            args.detector,
        )

        result = {
            "tool": "Auto-AVSR",
            "version": "v1.0.0",
            "mode": "visual",
            "device": "cpu",
            "source_video": str(source),
            "source_start": args.start,
            "source_duration_requested": args.duration,
            "test_clip": str(clip_path) if args.keep_clip else None,
            "auto_avsr_dir": str(auto_avsr_dir),
            "checkpoint": str(checkpoint),
            "detector": args.detector,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "return_code": returncode,
            "transcript": extract_transcript(stdout),
            "stdout": stdout,
            "stderr": stderr,
            "timestamp_note": (
                "Auto-AVSR v1.0.0 demo output is retained as raw evidence. "
                "This wrapper does not invent word-level timestamps."
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
