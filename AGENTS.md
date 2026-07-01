# AGENTS.md

## Project: shadow-agent

shadow-agent is a local-first tool for generating English shadowing study packs from audio or video files.

The MVP goal is:

1. Accept an input MP3 file.
2. Transcribe it with timestamps using faster-whisper.
3. Select valuable shadowing sentences.
4. Clip each sentence into a separate MP3 file.
5. Generate a study pack containing audio clips, transcript, translations, pronunciation notes, and a README.

---

## Tech Stack

Use the following stack for the first version:

- Python 3.11+
- faster-whisper for speech-to-text
- ffmpeg for audio/video processing
- pydub as a Python wrapper for simple clipping
- pathlib for file paths
- zipfile for packaging output
- JSON for intermediate transcript metadata

Do not introduce a web framework in the MVP unless explicitly requested.

---

## Development Principles

Keep the first version simple and runnable from the command line.

Prefer clear, readable code over clever abstractions.

The tool should work locally on macOS first.

Assume the user is learning both English and AI engineering, so code should be easy to understand and extend.

Use small modules with clear responsibilities.

Avoid over-engineering.

---

## Suggested Project Structure

```text
shadow-agent/
├── AGENTS.md
├── README.md
├── requirements.txt
├── input/
│   └── sample.mp3
├── output/
│   ├── transcript.json
│   ├── clips/
│   └── shadow_pack.zip
└── shadow_agent/
    ├── __init__.py
    ├── main.py
    ├── transcribe.py
    ├── clipper.py
    ├── selector.py
    ├── packer.py
    └── utils.py
```

---

## Module Responsibilities

### `main.py`

Command-line entry point.

Expected command:

```bash
python -m shadow_agent.main input/sample.mp3
```

Responsibilities:

- Parse input file path.
- Create output directory.
- Run transcription.
- Select target sentences.
- Clip audio.
- Generate study pack.

---

### `transcribe.py`

Responsible for converting audio into timestamped text.

Use `faster-whisper`.

Expected output format:

```json
[
  {
    "id": 1,
    "start": 132.12,
    "end": 148.45,
    "text": "Everything with email depends on the situation."
  }
]
```

Use seconds for `start` and `end`.

Default model:

```python
WhisperModel("small", device="cpu", compute_type="int8")
```

---

### `selector.py`

Responsible for choosing sentences worth shadowing.

MVP behavior:

- Allow user to provide target sentences manually.
- Match target sentences against transcript using fuzzy matching.
- Return matching transcript segments.

Future behavior:

- Use an LLM to score sentences by usefulness.
- Prefer sentences useful for work, meetings, technical communication, and natural spoken English.

Selection criteria:

- Useful expression
- Natural spoken rhythm
- Clear sentence boundary
- 5 to 30 seconds long
- Good for repetition
- Avoid intros, names, ads, and filler-only sentences

---

### `clipper.py`

Responsible for cutting audio clips.

Use either `pydub` or direct `ffmpeg`.

For pydub:

```python
audio = AudioSegment.from_mp3(input_path)
clip = audio[start_ms:end_ms]
clip.export(output_path, format="mp3")
```

Always add a small buffer:

- 0.5 seconds before start
- 0.8 seconds after end

Do not allow start time below 0.

Normalize output names:

```text
01_everything_with_email.mp3
02_really_nice_way_to_do_it.mp3
```

---

### `packer.py`

Responsible for generating the final study pack.

Output should include:

```text
output/
├── clips/
│   ├── 01_xxx.mp3
│   └── 02_xxx.mp3
├── clips_0.8x/
│   ├── 01_xxx_0.8x.mp3
│   └── 02_xxx_0.8x.mp3
├── transcript.json
├── README_学习说明.md
└── shadow_pack.zip
```

README should include:

- English sentence
- Chinese translation placeholder
- Key expressions
- Pronunciation notes
- Shadowing tips

---

## Coding Style

Use type hints where helpful.

Use `Path` instead of raw string paths.

Prefer pure functions where possible.

Handle errors clearly:

- Missing input file
- Unsupported file format
- Missing ffmpeg
- No transcript segments found
- No matching sentence found

Log progress with simple `print()` statements for now.

Example:

```text
[1/4] Transcribing audio...
[2/4] Selecting shadowing sentences...
[3/4] Clipping audio...
[4/4] Building study pack...
Done: output/shadow_pack.zip
```

---

## File Handling Rules

Do not overwrite user input files.

Write all generated files to `output/`.

If output already exists, either clean it safely or create a timestamped subdirectory.

Do not commit large MP3/MP4 files to git.

Add these to `.gitignore`:

```gitignore
input/*
output/*
*.mp3
*.mp4
*.wav
*.m4a
*.zip
.venv/
__pycache__/
```

---

## MVP Milestones

### Milestone 1

Implement:

```bash
python -m shadow_agent.main input/sample.mp3
```

Output:

```text
output/transcript.json
```

### Milestone 2

Add manual sentence selection.

Input:

```text
targets.txt
```

Output:

```text
output/selected_segments.json
```

### Milestone 3

Clip selected segments into MP3 files.

Output:

```text
output/clips/*.mp3
```

### Milestone 4

Generate study pack zip.

Output:

```text
output/shadow_pack.zip
```

### Milestone 5

Add optional LLM-based sentence scoring and explanation generation.

---

## Commands

Install dependencies:

```bash
brew install ffmpeg

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run:

```bash
python -m shadow_agent.main input/sample.mp3
```

---

## Requirements File

Initial `requirements.txt` should contain:

```txt
faster-whisper
pydub
rapidfuzz
```

Use `rapidfuzz` for fuzzy matching target sentences against transcript text.

---

## Important Notes for Codex

When generating code:

- Start with the MVP.
- Do not build a UI yet.
- Do not add Docker or Kubernetes yet.
- Do not add database storage yet.
- Keep all generated files local.
- Prefer simple, testable functions.
- Explain any non-obvious audio-processing logic in comments.
- Use English for code and comments.
- Use Chinese only in user-facing README content where helpful.

The first useful implementation should be small enough to understand in one sitting.
