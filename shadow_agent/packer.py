from __future__ import annotations

import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shadow_agent.study_notes import StudyNote

from shadow_agent.transcribe import TranscriptSegment
from shadow_agent.utils import format_timestamp


README_NAME = "README_学习说明.md"


def build_study_readme(
    selected_segments: list[TranscriptSegment],
    clip_records: list[dict[str, str | float | int]],
    output_path: Path,
    study_notes: list[StudyNote] | None = None,
) -> Path:
    clip_by_id = {int(record["id"]): record for record in clip_records}
    notes_by_text = {note["text"]: note for note in (study_notes or [])}
    lines = [
        "# Shadowing 学习说明",
        "",
        "发音提示是基于文本的练习建议，请结合原音频模仿实际重音、停顿和语调。",
        "",
        "这个学习包用于英语跟读练习。建议每个句子按以下节奏练习：先听原速，再看文本跟读，再听 0.8x 慢速，最后脱稿复述。",
        "",
    ]

    for index, segment in enumerate(selected_segments, start=1):
        record = clip_by_id.get(int(segment["id"]), {})
        clip_name = Path(str(record.get("clip", ""))).name
        slow_clip_name = Path(str(record.get("slow_clip", ""))).name
        start = format_timestamp(float(segment["start"]))
        end = format_timestamp(float(segment["end"]))
        note = notes_by_text.get(segment["text"])
        if study_notes is not None and note is None:
            raise ValueError(f"Missing study notes for sentence {index}.")

        lines.extend(
            [
                f"## {index:02d}. {segment['text']}",
                "",
                f"- Time: {start} - {end}",
                f"- Audio: `clips/{clip_name}`",
                f"- Slow audio: `clips_0.8x/{slow_clip_name}`",
                f"- 中文翻译：{_inline(note['translation']) if note else '未生成（已跳过学习讲解）'}",
                "- Key expressions:",
                *_note_items(note["key_expressions"] if note else []),
                "- Pronunciation notes:",
                *_note_items(note["pronunciation_notes"] if note else []),
                "- Shadowing tips: Listen once, repeat three times, then record yourself once.",
                "",
            ]
        )

    readme_path = output_path / README_NAME
    readme_path.write_text("\n".join(lines), encoding="utf-8")
    return readme_path


def _inline(text: str) -> str:
    return " ".join(text.splitlines()).strip()


def _note_items(items: list[str]) -> list[str]:
    return [f"  - {_inline(item)}" for item in items] or ["  - 未生成（已跳过学习讲解）"]


def build_zip(output_dir: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.rglob("*")):
            if path == zip_path or not path.is_file():
                continue
            archive.write(path, path.relative_to(output_dir))
    return zip_path

