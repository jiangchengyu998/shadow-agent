from __future__ import annotations

import zipfile
from pathlib import Path

from shadow_agent.transcribe import TranscriptSegment
from shadow_agent.utils import format_timestamp


README_NAME = "README_学习说明.md"


def build_study_readme(
    selected_segments: list[TranscriptSegment],
    clip_records: list[dict[str, str | float | int]],
    output_path: Path,
) -> Path:
    clip_by_id = {int(record["id"]): record for record in clip_records}
    lines = [
        "# Shadowing 学习说明",
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

        lines.extend(
            [
                f"## {index:02d}. {segment['text']}",
                "",
                f"- Time: {start} - {end}",
                f"- Audio: `clips/{clip_name}`",
                f"- Slow audio: `clips_0.8x/{slow_clip_name}`",
                "- 中文翻译：TODO",
                "- Key expressions: TODO",
                "- Pronunciation notes: TODO",
                "- Shadowing tips: Listen once, repeat three times, then record yourself once.",
                "",
            ]
        )

    readme_path = output_path / README_NAME
    readme_path.write_text("\n".join(lines), encoding="utf-8")
    return readme_path


def build_zip(output_dir: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.rglob("*")):
            if path == zip_path or not path.is_file():
                continue
            archive.write(path, path.relative_to(output_dir))
    return zip_path

