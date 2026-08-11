"""Unit tests for ai_analysis.py (prompt building and data prep, no model)."""

import json
from dataclasses import dataclass

import pytest

import ai_analysis
from ai_analysis import (
    LOCAL_JSON_SCHEMA,
    build_prompt,
    complete_results,
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

    def test_ambiguous_basename_dropped(self):
        files = self._files() + [
            FakeFile("nested_1.txt", "other/nested_1.txt", "other", None),
        ]
        results = [{"type": "file", "path": "dir_1/nested_1.txt", "suggested_folder": "Data"}]
        cleaned = sanitize_results(results, files)
        # Ambiguous (two files named nested_1.txt) - must not guess. The
        # entry is dropped; complete_results adds both real files back.
        assert cleaned == []

    def test_missing_path_dropped(self):
        results = [{"type": "file", "path": "nonexistent.txt", "suggested_folder": "Data"}]
        cleaned = sanitize_results(results, self._files())
        assert cleaned == []

    def test_dropped_paths_backfilled_by_complete_results(self):
        # The reported bug: AI returned "README.md" when two scanned files
        # share that name, so the basename is ambiguous. sanitize drops it,
        # complete_results adds both real files back in their folders.
        files = [
            FakeFile("README.md", "docs/README.md", "docs", None),
            FakeFile("README.md", "proj/README.md", "proj", None),
            FakeFile("notes.txt", "notes.txt", ".", None),
        ]
        results = [
            {"type": "file", "path": "README.md", "suggested_folder": "Docs", "suggested_name": "README.md"},
            {"type": "file", "path": "notes.txt", "suggested_folder": "Notes", "suggested_name": "notes.txt"},
        ]
        cleaned = sanitize_results(results, files)
        assert len(cleaned) == 1  # only notes.txt survives
        completed = complete_results(cleaned, files)
        paths = {r["path"] for r in completed}
        assert paths == {"docs/README.md", "proj/README.md", "notes.txt"}
        docs = next(r for r in completed if r["path"] == "docs/README.md")
        assert docs["suggested_folder"] == "docs"
        assert docs["suggested_name"] == "README.md"

    def test_projects_survive_when_file_paths_dropped(self):
        # Project entries must never be touched, even when file paths are
        # dropped in the same batch.
        files = [
            FakeFile("a.txt", "a.txt", ".", None),
            FakeFile("main.py", "app/src/main.py", "app/src", None),
        ]
        results = [
            {"type": "project", "path": "app", "suggested_folder": "Code"},
            {"type": "file", "path": "nope.txt", "suggested_folder": "X"},
        ]
        cleaned = sanitize_results(results, files)
        assert cleaned == [
            {"type": "project", "path": "app", "suggested_folder": "Code"}
        ]

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


class TestCompleteResults:
    def _files(self):
        return [
            FakeFile("a.txt", "a.txt", ".", None),
            FakeFile("notes.txt", "docs/notes.txt", "docs", None),
            FakeFile("main.py", "proj/src/main.py", "proj/src", None),
        ]

    def test_omitted_files_added_in_original_folder(self):
        # The AI only returned a.txt; docs/notes.txt and proj/src/main.py
        # were omitted and must be added back with their current folder.
        results = [
            {
                "type": "file",
                "path": "a.txt",
                "suggested_folder": "Root",
                "suggested_name": "a.txt",
            },
        ]
        completed = complete_results(results, self._files())
        assert len(completed) == 3

        notes = next(r for r in completed if r["path"] == "docs/notes.txt")
        assert notes["type"] == "file"
        assert notes["suggested_folder"] == "docs"
        assert notes["suggested_name"] == "notes.txt"

    def test_existing_results_not_duplicated(self):
        results = [
            {
                "type": "file",
                "path": "a.txt",
                "suggested_folder": "Root",
                "suggested_name": "a.txt",
            },
        ]
        completed = complete_results(results, self._files())
        assert sum(1 for r in completed if r["path"] == "a.txt") == 1

    def test_root_level_file_kept_at_organised_root(self):
        # A root-level file (parent_folder ".") omitted by the AI is added
        # back with the organised folder root as its destination.
        results = []
        completed = complete_results(results, self._files())
        root_file = next(r for r in completed if r["path"] == "a.txt")
        assert root_file["suggested_folder"] == "."
        assert root_file["suggested_name"] == "a.txt"

    def test_files_inside_returned_project_skipped(self):
        # proj/src/main.py lives inside the returned project "proj", so it
        # travels with the project copy and needs no individual entry.
        results = [
            {"type": "project", "path": "proj", "suggested_folder": "Code"},
        ]
        completed = complete_results(results, self._files())
        assert sum(1 for r in completed if r["path"] == "proj/src/main.py") == 0
        assert sum(1 for r in completed if r["path"] == "a.txt") == 1
        assert sum(1 for r in completed if r["path"] == "docs/notes.txt") == 1

    def test_input_not_mutated(self):
        results = [
            {
                "type": "file",
                "path": "a.txt",
                "suggested_folder": "Root",
                "suggested_name": "a.txt",
            },
        ]
        before = [dict(r) for r in results]
        complete_results(results, self._files())
        assert results == before
