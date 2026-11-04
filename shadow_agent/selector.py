from __future__ import annotations

import json
import math
import re
from difflib import SequenceMatcher
from pathlib import Path

from shadow_agent.transcribe import TranscriptSegment, load_transcript


SelectedSegment = TranscriptSegment

# Maximum consecutive transcript segments per manual-match candidate, NOT seconds or words.
# The per-target estimate below may be smaller. Increase for long targets split into many chunks;
# larger values cost more time/memory. Ignored by automatic selection and re-clipping.
MAX_MANUAL_TARGET_WINDOW_SIZE = 80


def load_selected_segments(path: Path) -> list[SelectedSegment]:
    segments = load_transcript(path.expanduser())
    if not segments:
        raise ValueError(f"No selected segments found in: {path}")
    seen_ids: set[int] = set()
    for index, segment in enumerate(segments, start=1):
        message = f"Invalid selected segment #{index} in {path}"
        if not isinstance(segment, dict):
            raise ValueError(f"{message}: expected an object.")
        segment_id = segment.get("id")
        if type(segment_id) is not int or segment_id in seen_ids:
            raise ValueError(f"{message}: id must be a unique integer.")
        seen_ids.add(segment_id)
        if not isinstance(segment.get("text"), str) or not segment["text"].strip():
            raise ValueError(f"{message}: text must be a non-empty string.")
        for key in ("start", "end"):
            value = segment.get(key)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{message}: {key} must be a finite number in seconds.")
        if not 0 <= segment["start"] < segment["end"]:
            raise ValueError(f"{message}: timestamps must satisfy 0 <= start < end.")
    return segments


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
    # min_score is a 0-100 similarity threshold after a length penalty, not a probability.
    # Lower values accept more matches but may select unrelated passages.
    if not transcript:
        raise RuntimeError("No transcript segments found.")
    if not all(segment.get("words") for segment in transcript):
        print("Warning: transcript lacks word timestamps; matching uses whole segments. "
              "Transcribe again for precise target boundaries.")

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
        else:
            print(f"Warning: target #{target_index} skipped: best score {score:.2f} "
                  f"is below --min-score {min_score}.")

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
            candidates.append(_trim_to_target(target, _merge_segments(window)))

    return candidates


def _merge_segments(segments: list[TranscriptSegment]) -> TranscriptSegment:
    merged = {
        "id": int(segments[0]["id"]),
        "source_ids": [int(segment["id"]) for segment in segments],
        "start": float(segments[0]["start"]),
        "end": float(segments[-1]["end"]),
        "text": " ".join(str(segment["text"]).strip() for segment in segments),
    }
    # Only trim when every source segment has word timing; never estimate times from text length.
    if all(segment.get("words") for segment in segments):
        merged["words"] = [
            dict(word, source_id=int(segment["id"]))
            for segment in segments for word in segment["words"]
        ]
    return merged


def _trim_to_target(target: str, candidate: TranscriptSegment) -> TranscriptSegment:
    words = candidate.get("words")
    if not words:
        return candidate
    target_tokens = _normalize_for_match(target).split()
    tokens: list[str] = []
    word_indices: list[int] = []
    for index, word in enumerate(words):
        normalized = _normalize_for_match(word["word"]).split()
        tokens.extend(normalized)
        word_indices.extend([index] * len(normalized))
    blocks = [block for block in SequenceMatcher(None, target_tokens, tokens, autojunk=False).get_matching_blocks() if block.size]
    if not blocks or not target_tokens:
        return candidate
    # Trim only anchored boundaries; unmatched target boundaries must still lose score.
    first, last = blocks[0], blocks[-1]
    start = word_indices[first.b] if first.a == 0 else 0
    end = word_indices[last.b + last.size - 1] + 1 if last.a + last.size == len(target_tokens) else len(words)
    kept = words[start:end]
    return {
        **candidate,
        "start": kept[0]["start"],
        "end": kept[-1]["end"],
        "text": " ".join(word["word"].strip() for word in kept),
        "source_ids": list(dict.fromkeys(word["source_id"] for word in kept)),
        "words": kept,
    }


def _guess_max_window_size(target: str) -> int:
    word_count = len(_normalize_for_match(target).split())
    sentence_marks = sum(target.count(mark) for mark in ".!?。！？")
    # faster-whisper often splits natural conversation into short 2-4 second chunks.
    # Long manual targets need enough adjacent chunks to cover the full requested passage.
    # Estimate from sentence marks (+4 chunks) or word count (8 words/chunk, +8 chunks).
    # These margins allow for transcription splitting a sentence into multiple chunks.
    return min(MAX_MANUAL_TARGET_WINDOW_SIZE, max(1, sentence_marks + 4, word_count // 8 + 8))


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
    # Keep 75% of similarity; scale the remaining 25% by relative text length.
    # This discourages candidates much longer or shorter than the target.
    score = base_score * (0.75 + 0.25 * length_ratio)
    # Whole-passage similarity can hide a missing opening/ending in long targets.
    # Compare up to five boundary words separately so completeness affects ranking.
    target_words = normalized_target.split()
    candidate_words = normalized_candidate.split()
    boundary_size = min(5, len(target_words))
    if boundary_size:
        opening = SequenceMatcher(None, target_words[:boundary_size], candidate_words[:boundary_size], autojunk=False).ratio()
        ending = SequenceMatcher(None, target_words[-boundary_size:], candidate_words[-boundary_size:], autojunk=False).ratio()
        score *= 0.6 + 0.2 * opening + 0.2 * ending
    return score


def auto_select_segments(
    transcript: list[TranscriptSegment],
    limit: int = 8,
) -> list[SelectedSegment]:
    selected: list[SelectedSegment] = []
    # limit caps automatic picks in transcript order; these exclusions are substring matches.
    blocked_words = {"subscribe", "sponsor", "advertisement", "intro", "welcome back"}

    for segment in transcript:
        text = str(segment["text"]).strip()
        duration = float(segment["end"]) - float(segment["start"])
        word_count = len(text.split())
        lower_text = text.lower()

        # Automatic selection only: accept durations of 5-30 seconds, inclusive.
        if duration < 5 or duration > 30:
            continue
        # Require at least five whitespace-separated words to avoid short utterances.
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
