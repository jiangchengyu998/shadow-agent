from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

from shadow_agent.transcribe import TranscriptSegment


SelectedSegment = TranscriptSegment


def load_targets(targets_path: Path) -> list[str]:
    if not targets_path.exists():
        raise FileNotFoundError(f"Targets file not found: {targets_path}")

    targets = [
        line.strip()
        for line in targets_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not targets:
        raise ValueError(f"No target sentences found in: {targets_path}")
    return targets


def select_by_targets(
    transcript: list[TranscriptSegment],
    targets: list[str],
    min_score: int = 70,
) -> list[SelectedSegment]:
    if not transcript:
        raise RuntimeError("No transcript segments found.")

    selected: list[SelectedSegment] = []
    seen_ids: set[int] = set()

    for target in targets:
        segment, score = _best_match(target, transcript)
        if segment is None:
            continue

        segment_id = int(segment["id"])
        if score >= min_score and segment_id not in seen_ids:
            item = dict(segment)
            item["target"] = target
            item["match_score"] = round(float(score), 2)
            selected.append(item)
            seen_ids.add(segment_id)

    if not selected:
        raise RuntimeError("No matching sentence found. Try lowering --min-score or editing targets.txt.")

    return selected


def _best_match(
    target: str,
    transcript: list[TranscriptSegment],
) -> tuple[TranscriptSegment | None, float]:
    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        return _best_match_with_difflib(target, transcript)

    choices = {str(segment["text"]): segment for segment in transcript}
    match = process.extractOne(target, choices.keys(), scorer=fuzz.token_set_ratio)
    if match is None:
        return None, 0.0

    matched_text, score, _index = match
    return choices[matched_text], float(score)


def _best_match_with_difflib(
    target: str,
    transcript: list[TranscriptSegment],
) -> tuple[TranscriptSegment | None, float]:
    best_segment: TranscriptSegment | None = None
    best_score = 0.0
    normalized_target = _normalize_for_match(target)

    for segment in transcript:
        normalized_text = _normalize_for_match(str(segment["text"]))
        score = SequenceMatcher(None, normalized_target, normalized_text).ratio() * 100
        if score > best_score:
            best_segment = segment
            best_score = score

    return best_segment, best_score


def _normalize_for_match(text: str) -> str:
    return " ".join(text.lower().split())


def auto_select_segments(
    transcript: list[TranscriptSegment],
    limit: int = 8,
) -> list[SelectedSegment]:
    selected: list[SelectedSegment] = []
    blocked_words = {"subscribe", "sponsor", "advertisement", "intro", "welcome back"}

    for segment in transcript:
        text = str(segment["text"]).strip()
        duration = float(segment["end"]) - float(segment["start"])
        word_count = len(text.split())
        lower_text = text.lower()

        if duration < 5 or duration > 30:
            continue
        if word_count < 5:
            continue
        if any(word in lower_text for word in blocked_words):
            continue

        selected.append(segment)
        if len(selected) >= limit:
            break

    if not selected:
        raise RuntimeError(
            "No suitable shadowing segments found automatically. Provide a targets.txt file."
        )
    return selected


def save_selected_segments(segments: list[SelectedSegment], output_path: Path) -> None:
    output_path.write_text(
        json.dumps(segments, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
