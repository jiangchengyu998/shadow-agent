from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TranscriptSegment = dict[str, Any]


def transcribe_audio(input_path: Path, model_size: str = "small") -> list[TranscriptSegment]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Run: pip install -r requirements.txt"
        ) from exc

    # model_size chooses the transcription model (default: small).
    # CPU + int8 keeps execution local and reduces model memory use on macOS.
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    # Word timestamps allow manual targets to start/end inside a Whisper segment.
    segments, _info = model.transcribe(str(input_path), word_timestamps=True)

    transcript: list[TranscriptSegment] = []
    for index, segment in enumerate(segments, start=1):
        text = segment.text.strip()
        if not text:
            continue
        transcript.append(
            {
                "id": index,
                "start": round(float(segment.start), 2),
                "end": round(float(segment.end), 2),
                "text": text,
                "words": [
                    {"word": word.word, "start": float(word.start), "end": float(word.end)}
                    for word in (segment.words or [])
                ],
            }
        )

    if not transcript:
        raise RuntimeError("No transcript segments found.")

    return transcript


def save_transcript(transcript: list[TranscriptSegment], output_path: Path) -> None:
    output_path.write_text(
        json.dumps(transcript, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_transcript(transcript_path: Path) -> list[TranscriptSegment]:
    data: Any = json.loads(transcript_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Transcript must be a list: {transcript_path}")
    return data
