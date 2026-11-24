import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from shadow_agent.packer import README_NAME, build_study_readme
from shadow_agent.study_notes import (
    MAX_NOTE_ATTEMPTS,
    NOTES_NAME,
    enrich_study_pack,
    expression_in_text,
    generate_study_notes,
    load_study_notes,
    request_note,
    save_study_notes,
)


TEXT = "Everything with email depends on the situation."
CONTENT = {
    "translation": "邮件相关的事都要视情况而定。",
    "key_expressions": ["depend on：取决于。例句：It depends on the weather."],
    "pronunciation_notes": ["可尝试重读 EMAIL 和 SITUATION，突出主题和条件。"],
}


def segment(text=TEXT, segment_id=1):
    return {"id": segment_id, "text": text, "start": 1.0, "end": 6.0}


def note(text=TEXT, segment_id=1):
    return {"id": segment_id, "text": text, "model": "test-model", **CONTENT}


class StudyNotesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.path = self.directory / NOTES_NAME

    def test_saved_manual_edits_reused_without_client_even_when_id_changes(self):
        saved = {**note(), "translation": "自己修改的译文"}
        save_study_notes([saved], self.path)
        with patch("shadow_agent.study_notes.create_client") as client:
            result = generate_study_notes([segment(segment_id=99)], self.path)
        client.assert_not_called()
        self.assertEqual(result[0]["translation"], "自己修改的译文")
        self.assertEqual(result[0]["id"], 99)

    def test_changed_text_with_same_id_requires_new_notes(self):
        save_study_notes([note()], self.path)
        with patch("shadow_agent.study_notes.create_client", return_value=MagicMock()), patch(
            "shadow_agent.study_notes.request_note", return_value=CONTENT
        ) as request:
            result = generate_study_notes([segment("It depends on the weather.")], self.path)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(result[0]["text"], "It depends on the weather.")

    def test_failure_preserves_first_sentence_and_resume_requests_only_missing(self):
        segments = [segment(), segment("Why don't you join us?", 2)]
        with patch("shadow_agent.study_notes.create_client", return_value=MagicMock()), patch(
            "shadow_agent.study_notes.request_note", side_effect=[CONTENT, RuntimeError("network")]
        ), self.assertRaisesRegex(RuntimeError, "network"):
            generate_study_notes(segments, self.path)
        self.assertEqual(len(load_study_notes(self.path)), 1)
        with patch("shadow_agent.study_notes.create_client", return_value=MagicMock()), patch(
            "shadow_agent.study_notes.request_note", return_value=CONTENT
        ) as request:
            result = generate_study_notes(segments, self.path)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(len(result), 2)

    def test_malformed_cache_is_reported_without_overwriting_it(self):
        original = json.dumps([{**note(), "key_expressions": []}])
        self.path.write_text(original)
        with self.assertRaises(ValueError):
            generate_study_notes([segment()], self.path)
        self.assertEqual(self.path.read_text(), original)

    def test_readme_matches_original_text_instead_of_old_ids(self):
        result = build_study_readme([segment(segment_id=42)], [], self.directory, [note()])
        text = result.read_text()
        self.assertIn(CONTENT["translation"], text)
        self.assertIn(CONTENT["key_expressions"][0], text)
        self.assertIn(CONTENT["pronunciation_notes"][0], text)
        self.assertNotIn("TODO", text)

    def test_incomplete_notes_do_not_replace_existing_readme(self):
        path = self.directory / README_NAME
        path.write_text("original")
        with self.assertRaisesRegex(ValueError, "Missing study notes"):
            build_study_readme([segment()], [], self.directory, [])
        self.assertEqual(path.read_text(), "original")

    def test_enrich_existing_pack_updates_zip_without_transcription(self):
        (self.directory / "selected_segments.json").write_text(json.dumps([segment()]))
        (self.directory / "clips.json").write_text(json.dumps([
            {"id": 1, "clip": "clips/test.mp3", "slow_clip": "clips_0.8x/test.mp3"}
        ]))
        (self.directory / "clips").mkdir()
        (self.directory / "clips" / "test.mp3").write_bytes(b"unchanged audio")
        save_study_notes([note()], self.path)
        with patch("shadow_agent.study_notes.create_client") as client:
            zip_path = enrich_study_pack(self.directory)
        client.assert_not_called()
        with zipfile.ZipFile(zip_path) as archive:
            self.assertIn(NOTES_NAME, archive.namelist())
            self.assertNotIn("shadow_pack.zip", archive.namelist())
            self.assertEqual(archive.read("clips/test.mp3"), b"unchanged audio")
            self.assertIn(CONTENT["translation"], archive.read(README_NAME).decode())


class ResponseTests(unittest.TestCase):
    def test_formatting_variants_match_without_accepting_changed_words(self):
        matches = [
            ("go-to solution", "the first go -to solution for heat"),
            ("go to solution", "the first go–to solution for heat"),
            ("you're not alone", "You’re not alone."),
            ("weʼre going", "We're going to face it."),
            ("air conditioning", "AIR\n  CONDITIONING helps."),
            ("café", "A café nearby."),
        ]
        for expression, text in matches:
            with self.subTest(expression=expression, text=text):
                self.assertTrue(expression_in_text(expression, text))
        for expression in ("on", "dit", "", "...", "air cools", "be detrimental"):
            with self.subTest(expression=expression):
                self.assertFalse(expression_in_text(expression, "Air conditioning is detrimental."))

    def test_aircon_hyphen_spacing_renders_without_retry(self):
        data = {**CONTENT, "key_expressions": [{
            "expression": "go-to solution", "meaning": "首选方案",
            "usage": "表示优先采用的办法。", "example": "This is my go-to solution.",
        }]}
        client = MagicMock()
        client.responses.create.return_value = SimpleNamespace(
            status="completed", output_text=json.dumps(data)
        )
        result = request_note(client, "Air conditioning is the first go -to solution.", "test-model")
        self.assertIn("go-to solution", result["key_expressions"][0])
        self.assertEqual(client.responses.create.call_count, 1)

    def test_invalid_expression_is_corrected_using_validation_feedback(self):
        expression = {"expression": "depend on", "meaning": "取决于", "usage": "说明决定因素。",
                      "example": "It depends on the weather."}
        invalid = {**CONTENT, "key_expressions": [expression]}
        valid = {**CONTENT, "key_expressions": [{**expression, "expression": "depends on"}]}
        client = MagicMock()
        client.responses.create.side_effect = [
            SimpleNamespace(status="completed", output_text=json.dumps(invalid)),
            SimpleNamespace(status="completed", output_text=json.dumps(valid)),
        ]
        result = request_note(client, TEXT, "test-model")
        self.assertIn("depends on", result["key_expressions"][0])
        self.assertEqual(client.responses.create.call_count, 2)
        feedback = client.responses.create.call_args.kwargs["input"][-1]["content"]
        self.assertIn("depend on", feedback)
        self.assertIn("verb forms", feedback)

    def test_expression_fields_render_with_meaning_usage_and_example(self):
        data = {**CONTENT, "key_expressions": [{
            "expression": "depends on", "meaning": "取决于",
            "usage": "用于说明决定因素。", "example": "It depends on the weather.",
        }]}
        client = MagicMock()
        client.responses.create.return_value = SimpleNamespace(
            status="completed", output_text=json.dumps(data)
        )
        result = request_note(client, TEXT, "test-model")
        self.assertIn("取决于", result["key_expressions"][0])
        self.assertIn("用于说明决定因素", result["key_expressions"][0])
        self.assertIn("It depends on the weather.", result["key_expressions"][0])

    def test_expression_not_in_source_is_rejected(self):
        data = {**CONTENT, "key_expressions": [{
            "expression": "made up phrase", "meaning": "含义",
            "usage": "用法", "example": "An example.",
        }]}
        client = MagicMock()
        client.responses.create.return_value = SimpleNamespace(
            status="completed", output_text=json.dumps(data)
        )
        with self.assertRaisesRegex(RuntimeError, "invalid study notes"):
            request_note(client, TEXT, "test-model")
        self.assertEqual(client.responses.create.call_count, MAX_NOTE_ATTEMPTS)

    def test_refused_incomplete_and_empty_responses_are_not_accepted(self):
        for status, text in (("completed", ""), ("incomplete", "{}")):
            with self.subTest(status=status):
                client = MagicMock()
                client.responses.create.return_value = SimpleNamespace(status=status, output_text=text)
                with self.assertRaisesRegex(RuntimeError, "no complete study notes"):
                    request_note(client, TEXT, "test-model")
                self.assertEqual(client.responses.create.call_count, 1)

    def test_malformed_or_empty_fields_are_not_accepted(self):
        for data in ("not json", "[]", json.dumps({**CONTENT, "translation": ""})):
            with self.subTest(data=data):
                client = MagicMock()
                client.responses.create.return_value = SimpleNamespace(status="completed", output_text=data)
                with self.assertRaisesRegex(RuntimeError, "invalid study notes"):
                    request_note(client, TEXT, "test-model")


if __name__ == "__main__":
    unittest.main()
