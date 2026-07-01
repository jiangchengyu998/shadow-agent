from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path


SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".mp4", ".wav", ".m4a"}


def validate_input_file(input_path: Path) -> Path:
    path = input_path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Input path is not a file: {path}")
    if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
        raise ValueError(f"Unsupported file format '{path.suffix}'. Supported: {supported}")
    return path


def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg was not found. Install it with: brew install ffmpeg")


def create_output_dir(base_dir: Path = Path("output")) -> Path:
    base_dir = base_dir.resolve()
    if not base_dir.exists():
        base_dir.mkdir(parents=True)
        return base_dir

    if not any(base_dir.iterdir()):
        return base_dir

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_dir / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def slugify(text: str, max_words: int = 6) -> str:
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    slug = "_".join(words[:max_words])
    return slug or "clip"


def format_timestamp(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining = seconds - (minutes * 60)
    return f"{minutes:02d}:{remaining:05.2f}"

