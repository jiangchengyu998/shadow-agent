from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from shadow_agent.clipper import clip_segments, save_clip_records
from shadow_agent.packer import build_study_readme, build_zip
from shadow_agent.selector import (
    auto_select_segments,
    load_targets,
    load_selected_segments,
    save_selected_segments,
    select_by_targets,
)
from shadow_agent.transcribe import save_transcript, transcribe_audio
from shadow_agent.utils import create_output_dir, ensure_ffmpeg, validate_input_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an English shadowing study pack from an audio file.",
    )
    parser.add_argument("input", type=Path, help="Input audio/video file, for example input/sample.mp3")
    parser.add_argument(
        "--selected-segments",
        type=Path,
        help="Reclip an edited selected_segments.json, skipping transcription and selection.",
    )
    parser.add_argument(
        "--targets",
        type=Path,
        default=Path("targets.txt"),
        help="Optional target sentence file. Defaults to targets.txt if it exists.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Output directory. Defaults to output/.",
    )
    # Larger models generally need more memory/time; ignored when re-clipping.
    parser.add_argument(
        "--model",
        default="small",
        help="faster-whisper model size. Defaults to small.",
    )
    # Manual matching threshold (0-100); lower values accept more, potentially worse matches.
    parser.add_argument(
        "--min-score",
        type=int,
        default=70,
        help="Minimum fuzzy match score for manual targets. Defaults to 70.",
    )
    return parser.parse_args()


def run() -> Path:
    args = parse_args()
    input_path = validate_input_file(args.input)
    ensure_ffmpeg()
    if args.selected_segments is not None:
        print("[1/4] Loading selected segments (skipping transcription)...")
        selected_segments = load_selected_segments(args.selected_segments)
        output_dir = create_output_dir(args.output)
        original_transcript = args.selected_segments.expanduser().parent / "transcript.json"
        if original_transcript.is_file():
            shutil.copyfile(original_transcript, output_dir / "transcript.json")
        print("[2/4] Using edited timestamps (skipping selection)...")
    else:
        target_prefix = args.targets.stem if args.targets.is_file() else None
        output_dir = create_output_dir(args.output, prefix=target_prefix)
        print("[1/4] Transcribing audio...")
        transcript = transcribe_audio(input_path, model_size=args.model)
        transcript_path = output_dir / "transcript.json"
        save_transcript(transcript, transcript_path)

        print("[2/4] Selecting shadowing sentences...")
        if args.targets.exists():
            targets = load_targets(args.targets)
            selected_segments = select_by_targets(transcript, targets, min_score=args.min_score)
        else:
            selected_segments = auto_select_segments(transcript)
    selected_path = output_dir / "selected_segments.json"
    save_selected_segments(selected_segments, selected_path)

    print("[3/4] Clipping audio...")
    clip_records = clip_segments(
        input_path=input_path,
        segments=selected_segments,
        clips_dir=output_dir / "clips",
        slow_clips_dir=output_dir / "clips_0.8x",
    )
    save_clip_records(clip_records, output_dir / "clips.json")

    print("[4/4] Building study pack...")
    build_study_readme(selected_segments, clip_records, output_dir)
    zip_path = build_zip(output_dir, output_dir / "shadow_pack.zip")

    print(f"Done: {zip_path}")
    return zip_path


def main() -> None:
    try:
        run()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
