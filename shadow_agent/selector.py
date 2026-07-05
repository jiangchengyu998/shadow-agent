from __future__ import annotations

import json
import re
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

    for target_index, target in enumerate(targets, start=1):
        segment, score = _best_match(target, transcript)
        if segment is None:
            continue

        if score >= min_score:
            item = dict(segment)
            item["id"] = len(selected) + 1
            item["target_index"] = target_index
            item["target"] = target
            item["match_score"] = round(float(score), 2)
            selected.append(item)

    if not selected:
        raise RuntimeError("No matching sentence found. Try lowering --min-score or editing targets.txt.")

    return selected


def _best_match(
    target: str,
    transcript: list[TranscriptSegment],
) -> tuple[TranscriptSegment | None, float]:
    try:
        from rapidfuzz import fuzz
    except ImportError:
        return _best_match_with_difflib(target, transcript)

    best_segment: TranscriptSegment | None = None
    best_score = 0.0

    for candidate in _candidate_windows(target, transcript):
        score = _length_aware_score(
            target,
            str(candidate["text"]),
            base_score=float(fuzz.ratio(_normalize_for_match(target), _normalize_for_match(str(candidate["text"])))),
        )
        if score > best_score:
            best_segment = candidate
            best_score = score

    return best_segment, best_score


def _best_match_with_difflib(
    target: str,
    transcript: list[TranscriptSegment],
) -> tuple[TranscriptSegment | None, float]:
    best_segment: TranscriptSegment | None = None
    best_score = 0.0
    normalized_target = _normalize_for_match(target)

    for candidate in _candidate_windows(target, transcript):
        normalized_text = _normalize_for_match(str(candidate["text"]))
        score = _length_aware_score(
            normalized_target,
            normalized_text,
            base_score=SequenceMatcher(None, normalized_target, normalized_text).ratio() * 100,
        )
        if score > best_score:
            best_segment = candidate
            best_score = score

    return best_segment, best_score


def _candidate_windows(
    target: str,
    transcript: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    max_window_size = _guess_max_window_size(target)
    candidates: list[TranscriptSegment] = []

    for start_index in range(len(transcript)):
        end_limit = min(len(transcript), start_index + max_window_size)
        for end_index in range(start_index, end_limit):
            window = transcript[start_index : end_index + 1]
            candidates.append(_merge_segments(window))

    return candidates


def _merge_segments(segments: list[TranscriptSegment]) -> TranscriptSegment:
    return {
        "id": int(segments[0]["id"]),
        "source_ids": [int(segment["id"]) for segment in segments],
        "start": float(segments[0]["start"]),
        "end": float(segments[-1]["end"]),
        "text": " ".join(str(segment["text"]).strip() for segment in segments),
    }


def _guess_max_window_size(target: str) -> int:
    word_count = len(_normalize_for_match(target).split())
    sentence_marks = sum(target.count(mark) for mark in ".!?。！？")
    return min(40, max(1, sentence_marks + 4, word_count // 3 + 3))


def _normalize_for_match(text: str) -> str:
    text = text.lower().replace("’", "'").replace("…", " ")
    text = re.sub(r"[^a-z0-9']+", " ", text)
    return " ".join(text.split())


def _length_aware_score(target: str, candidate: str, base_score: float) -> float:
    normalized_target = _normalize_for_match(target)
    normalized_candidate = _normalize_for_match(candidate)
    longest = max(len(normalized_target), len(normalized_candidate))
    if longest == 0:
        return 0.0

    shortest = min(len(normalized_target), len(normalized_candidate))
    length_ratio = shortest / longest
    return base_score * (0.75 + 0.25 * length_ratio)


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
