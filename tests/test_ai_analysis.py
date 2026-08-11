"""Unit tests for ai_analysis.py (prompt building and data prep, no model)."""

import json
from dataclasses import dataclass

import pytest

import ai_analysis
from ai_analysis import (
    LOCAL_JSON_SCHEMA,
    build_prompt,
    create_local_grammar,
    prepare_ai_data,
    sanitize_results,
)


@dataclass
class FakeFile:
    name: str
    full_path: str
    parent_folder: str
    contents: str | None


@dataclass
class FakeFolder:
    name: str
    full_path: str


class TestPrepareAiData:
    def test_serializes_all_inputs(self):
        files = [
            FakeFile("a.py", "proj/a.py", "proj", "print(1)"),
            FakeFile("b.txt", "b.txt", ".", None),
        ]
        folders = [FakeFolder("proj", "proj")]
        project_roots = {"proj"}

        files_json, folders_json, roots_json = prepare_ai_data(
            files, folders, project_roots
        )

        parsed_files = json.loads(files_json)
        parsed_folders = json.loads(folders_json)
        parsed_roots = json.loads(roots_json)

        assert len(parsed_files) == 2
        assert parsed_files[0]["full_path"] == "proj/a.py"
        assert parsed_files[1]["contents"] is None
        assert parsed_folders[0]["name"] == "proj"
        assert parsed_roots == ["proj"]

    def test_empty_inputs(self):
        files_json, folders_json, roots_json = prepare_ai_data([], [], set())
        assert json.loads(files_json) == []
        assert json.loads(folders_json) == []
        assert json.loads(roots_json) == []


class TestBuildPrompt:
    def test_prompt_contains_all_inputs(self):
        prompt = build_prompt(
            '[{"path": "a.txt"}]',
            '[{"name": "docs"}]',
            '["proj"]',
        )
        assert "a.txt" in prompt
        assert "docs" in prompt
        assert "proj" in prompt

    def test_prompt_contains_rules(self):
        prompt = build_prompt("[]", "[]", "[]")
        assert "Every input item must appear exactly once" in prompt
        assert "Never use absolute paths" in prompt
        assert "suggested_folder" in prompt

    def test_unicode_content_preserved(self):
        prompt = build_prompt('[{"full_path": "café/naïve.txt"}]', "[]", "[]")
        assert "café/naïve.txt" in prompt


class TestLocalSchema:
    def test_schema_is_valid_json(self):
        json.dumps(LOCAL_JSON_SCHEMA)

    def test_schema_requires_type_and_path(self):
        required = LOCAL_JSON_SCHEMA["items"]["required"]
        assert "type" in required
        assert "path" in required
        assert "suggested_folder" in required

    def test_schema_allows_only_file_and_project(self):
        enum = LOCAL_JSON_SCHEMA["items"]["properties"]["type"]["enum"]
        assert set(enum) == {"file", "project"}

    def test_grammar_creatable_without_model(self):
        # Creating the grammar object does not load the model.
        grammar = create_local_grammar()
        assert grammar is not None


class TestSanitizeResults:
    def _files(self):
        return [
            FakeFile("nested_1.txt", "dir_1/sub/nested_1.txt", "dir_1/sub", None),
            FakeFile("binary_1.dat", "dir_1/sub/binary_1.dat", "dir_1/sub", None),
            FakeFile("notes.txt", "notes.txt", ".", None),
            FakeFile("readme.md", "proj/readme.md", "proj", None),
        ]

    def test_exact_paths_unchanged(self):
        results = [
            {"type": "file", "path": "notes.txt", "suggested_folder": "Docs"},
            {
                "type": "file",
                "path": "proj/readme.md",
                "suggested_folder": "Docs",
            },
        ]
        cleaned = sanitize_results(results, self._files())
        assert cleaned == results

    def test_truncated_path_repaired_by_unique_basename(self):
        # The AI dropped the 'sub' component - this is the reported bug.
        results = [
            {
                "type": "file",
                "path": "dir_1/nested_1.txt",
                "suggested_folder": "Data",
            },
            {
                "type": "file",
                "path": "dir_1/binary_1.dat",
                "suggested_folder": "Data",
            },
        ]
        cleaned = sanitize_results(results, self._files())
        assert cleaned[0]["path"] == "dir_1/sub/nested_1.txt"
        assert cleaned[1]["path"] == "dir_1/sub/binary_1.dat"

    def test_ambiguous_basename_left_untouched(self):
        files = self._files() + [
            FakeFile("nested_1.txt", "other/nested_1.txt", "other", None),
        ]
        results = [{"type": "file", "path": "dir_1/nested_1.txt", "suggested_folder": "Data"}]
        cleaned = sanitize_results(results, files)
        # Ambiguous (two files named nested_1.txt) - must not guess.
        assert cleaned[0]["path"] == "dir_1/nested_1.txt"

    def test_missing_path_kept(self):
        results = [{"type": "file", "path": "nonexistent.txt", "suggested_folder": "Data"}]
        cleaned = sanitize_results(results, self._files())
        assert cleaned[0]["path"] == "nonexistent.txt"

    def test_windows_backslashes_repaired(self):
        files = self._files()
        results = [{"type": "file", "path": "dir_1\\nested_1.txt", "suggested_folder": "Data"}]
        cleaned = sanitize_results(results, files)
        assert cleaned[0]["path"] == "dir_1/sub/nested_1.txt"

    def test_project_paths_left_untouched(self):
        # Project paths must stay relative to the organized folder (apply.py
        # relies on that), so the sanitizer must not rewrite them.
        results = [{"type": "project", "path": "WeatherApp", "suggested_folder": "Programming"}]
        cleaned = sanitize_results(results, [])
        assert cleaned[0]["path"] == "WeatherApp"

    def test_input_not_mutated(self):
        results = [{"type": "file", "path": "dir_1/nested_1.txt", "suggested_folder": "Data"}]
        before = [dict(r) for r in results]
        sanitize_results(results, self._files())
        assert results == before
