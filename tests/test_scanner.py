"""Unit tests for scanner.py (no AI model required)."""

from pathlib import Path

import pytest

import scanner


def _make_tree(root: Path, structure: dict):
    """Create a directory tree from a {path: content-or-None} mapping.

    A value of None creates a directory; a str creates a text file.
    """
    for rel, content in structure.items():
        path = root / rel
        if content is None:
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


class TestDetectProjects:
    def test_pyproject_toml_detects_project(self, tmp_path):
        _make_tree(tmp_path, {"myapp/pyproject.toml": "[project]\n"})
        roots = scanner.detect_projects(tmp_path)
        assert Path("myapp") in {p.relative_to(tmp_path) for p in roots}

    def test_package_json_detects_project(self, tmp_path):
        _make_tree(tmp_path, {"webapp/package.json": "{}"})
        roots = scanner.detect_projects(tmp_path)
        assert Path("webapp") in {p.relative_to(tmp_path) for p in roots}

    def test_dot_git_dir_detects_project(self, tmp_path):
        _make_tree(tmp_path, {"repo/.git/": None})
        roots = scanner.detect_projects(tmp_path)
        assert Path("repo") in {p.relative_to(tmp_path) for p in roots}

    def test_weak_markers_do_not_detect_project(self, tmp_path):
        # README.md alone is only 20 points - not enough to be a project.
        _make_tree(tmp_path, {"notes/README.md": "# Notes"})
        roots = scanner.detect_projects(tmp_path)
        assert Path("notes") not in {p.relative_to(tmp_path) for p in roots}

    def test_sln_pattern_detects_project(self, tmp_path):
        _make_tree(tmp_path, {"app/App.sln": ""})
        roots = scanner.detect_projects(tmp_path)
        assert Path("app") in {p.relative_to(tmp_path) for p in roots}

    def test_empty_dir_no_projects(self, tmp_path):
        _make_tree(tmp_path, {"empty/": None})
        assert scanner.detect_projects(tmp_path) == set()

    def test_nested_project_detected(self, tmp_path):
        _make_tree(tmp_path, {"outer/mid/proj/go.mod": "module x"})
        roots = {p.relative_to(tmp_path) for p in scanner.detect_projects(tmp_path)}
        assert Path("outer/mid/proj") in roots


class TestScanDirectory:
    def test_scans_files_and_folders(self, tmp_path, monkeypatch):
        # Avoid loading the LLM: replace summarize_content with a stub.
        monkeypatch.setattr(scanner, "summarize_content", lambda c: "stub summary")

        _make_tree(
            tmp_path,
            {
                "photos/": None,
                "photos/cat.png": "\xff\x00binary",
                "readme.txt": "hello world",
                "docs/": None,
                "docs/notes.txt": "some notes",
            },
        )

        files, folders, passthrough = scanner.scan_directory(tmp_path)

        file_names = {f.name for f in files}
        folder_names = {f.name for f in folders}
        assert file_names == {"cat.png", "readme.txt", "notes.txt"}
        assert folder_names == {"photos", "docs"}
        assert passthrough == []

    def test_passthrough_dirs_excluded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scanner, "summarize_content", lambda c: "stub summary")

        _make_tree(
            tmp_path,
            {
                "node_modules/": None,
                "node_modules/pkg/index.js": "x",
                ".venv/": None,
                ".venv/bin/python": "x",
                "main.py": "print(1)",
            },
        )

        files, folders, passthrough = scanner.scan_directory(tmp_path)

        file_names = {f.name for f in files}
        folder_names = {f.name for f in folders}
        # Passthrough contents must never appear.
        assert file_names == {"main.py"}
        assert folder_names == set()
        assert sorted(str(p) for p in passthrough) == [".venv", "node_modules"]

    def test_binary_files_skipped_by_summarizer(self, tmp_path, monkeypatch):
        calls = []

        def fake_summarize(content):
            calls.append(content)
            return "stub"

        monkeypatch.setattr(scanner, "summarize_content", fake_summarize)

        _make_tree(tmp_path, {"a.txt": "text"})
        # Real invalid UTF-8 bytes - must be written as bytes, not text.
        (tmp_path / "b.bin").write_bytes(b"\xff\xfe\x00\x01")

        files, _, _ = scanner.scan_directory(tmp_path)
        contents = {f.contents for f in files}
        assert None in contents  # binary file has no summary
        assert "stub" in contents
        assert len(calls) == 1  # only the text file reached the summarizer
