from __future__ import annotations

import json
from pathlib import Path

from shadow_agent.transcribe import TranscriptSegment
from shadow_agent.utils import slugify


PRE_BUFFER_SECONDS = 0.5
POST_BUFFER_SECONDS = 0.8


def clip_segments(
    input_path: Path,
    segments: list[TranscriptSegment],
    clips_dir: Path,
    slow_clips_dir: Path,
) -> list[dict[str, str | float | int]]:
    try:
        from pydub import AudioSegment
    except ImportError as exc:
        raise RuntimeError("pydub is not installed. Run: pip install -r requirements.txt") from exc

    clips_dir.mkdir(parents=True, exist_ok=True)
    slow_clips_dir.mkdir(parents=True, exist_ok=True)

    audio = AudioSegment.from_file(input_path)
    results: list[dict[str, str | float | int]] = []

    for index, segment in enumerate(segments, start=1):
        start_seconds = max(0.0, float(segment["start"]) - PRE_BUFFER_SECONDS)
        end_seconds = float(segment["end"]) + POST_BUFFER_SECONDS
        start_ms = int(start_seconds * 1000)
        end_ms = min(len(audio), int(end_seconds * 1000))

        if end_ms <= start_ms:
            raise ValueError(f"Invalid clip range for segment {segment['id']}")

        name = f"{index:02d}_{slugify(str(segment['text']))}.mp3"
        clip_path = clips_dir / name
        slow_clip_path = slow_clips_dir / name.replace(".mp3", "_0.8x.mp3")

        clip = audio[start_ms:end_ms]
        clip.export(clip_path, format="mp3")

        # Lowering frame rate changes playback speed while keeping pitch handling simple for the MVP.
        slow_clip = clip._spawn(clip.raw_data, overrides={"frame_rate": int(clip.frame_rate * 0.8)})
        slow_clip = slow_clip.set_frame_rate(clip.frame_rate)
        slow_clip.export(slow_clip_path, format="mp3")

        results.append(
            {
                "id": int(segment["id"]),
                "text": str(segment["text"]),
                "start": float(segment["start"]),
                "end": float(segment["end"]),
                "clip": str(clip_path),
                "slow_clip": str(slow_clip_path),
            }
        )

    return results


def save_clip_records(records: list[dict[str, str | float | int]], output_path: Path) -> None:
    output_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
