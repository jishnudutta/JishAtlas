"""Unit tests for apply.py: organized copy, path safety, verification."""

from pathlib import Path

import pytest

from apply import (
    _hash_file,
    _safe_destination,
    _safe_source,
    apply_changes_diff_folder,
    apply_changes_same_folder,
    create_organized_copy,
    verify_complete_copy,
)


class TestSafeSource:
    def test_normal_path_ok(self, tmp_path):
        target = tmp_path / "file.txt"
        target.write_text("hi")
        assert _safe_source(tmp_path, Path("file.txt")) == target

    def test_path_escape_rejected(self, tmp_path, tmp_path_factory):
        outside = tmp_path_factory.mktemp("outside")
        victim = outside / "secret.txt"
        victim.write_text("secret")

        result = _safe_source(tmp_path, Path("../outside/secret.txt"))
        assert result is None

    def test_absolute_path_outside_folder_rejected(self, tmp_path, tmp_path_factory):
        outside = tmp_path_factory.mktemp("outside")
        victim = outside / "secret.txt"
        victim.write_text("secret")

        # An absolute path pointing outside the folder must be rejected.
        result = _safe_source(tmp_path, victim)
        assert result is None


class TestSafeDestination:
    def test_normal_destination_ok(self, tmp_path):
        dest = _safe_destination(tmp_path, "Music", "song.mp3")
        assert dest == tmp_path / "Music" / "song.mp3"

    def test_escape_rejected(self, tmp_path):
        assert _safe_destination(tmp_path, "..", "evil.txt") is None
        assert _safe_destination(tmp_path, "../outside", "evil.txt") is None


class TestOrganizedCopy:
    def _make_source(self, root: Path):
        (root / "photos").mkdir(parents=True)
        (root / "photos" / "vacation.jpg").write_bytes(b"jpgdata")
        (root / "report.pdf").write_bytes(b"pdfdata")
        (root / "scripts").mkdir(parents=True)
        (root / "scripts" / "tool.py").write_text("print('x')")
        # A project root that must be moved as a single unit.
        (root / "WeatherApp").mkdir(parents=True)
        (root / "WeatherApp" / "pyproject.toml").write_text("[project]\n")
        (root / "WeatherApp" / "src").mkdir()
        (root / "WeatherApp" / "src" / "main.py").write_text("print('w')")
        # A passthrough directory that must be copied wholesale.
        (root / "node_modules").mkdir(parents=True)
        (root / "node_modules" / "pkg").mkdir()
        (root / "node_modules" / "pkg" / "index.js").write_text("x")

    def _results(self):
        return [
            {
                "type": "file",
                "path": "photos/vacation.jpg",
                "suggested_folder": "Media/Pictures",
                "suggested_name": "vacation.jpg",
            },
            {
                "type": "file",
                "path": "report.pdf",
                "suggested_folder": "Documents",
                "suggested_name": "report_2024.pdf",
            },
            {
                "type": "file",
                "path": "scripts/tool.py",
                "suggested_folder": "Code",
                "suggested_name": "tool.py",
            },
            {
                "type": "project",
                "path": "WeatherApp",
                "suggested_folder": "Programming",
            },
        ]

    def test_copy_mode_creates_organized_folder(self, tmp_path):
        source = tmp_path / "messy"
        self._make_source(source)

        passthrough_dirs = [Path("node_modules")]
        new_folder, stats = create_organized_copy(
            self._results(), source, passthrough_dirs
        )

        assert new_folder.name == "messy_Organised"
        assert new_folder.is_dir()

        # Files landed in their suggested folders.
        assert (new_folder / "Media/Pictures/vacation.jpg").read_bytes() == b"jpgdata"
        assert (new_folder / "Documents/report_2024.pdf").read_bytes() == b"pdfdata"
        assert (new_folder / "Code/tool.py").read_text() == "print('x')"

        # The project was moved as a whole, keeping its name.
        assert (new_folder / "Programming/WeatherApp/pyproject.toml").is_file()
        assert (new_folder / "Programming/WeatherApp/src/main.py").is_file()

        # Passthrough dir copied verbatim.
        assert (new_folder / "node_modules/pkg/index.js").read_text() == "x"

        assert stats["errors"] == 0
        assert stats["files_copied"] == 3
        assert stats["projects_copied"] == 1
        assert stats["passthrough_copied"] == 1

    def test_original_folder_untouched_in_copy_mode(self, tmp_path):
        source = tmp_path / "messy"
        self._make_source(source)
        before = sorted(str(p.relative_to(source)) for p in source.rglob("*"))

        create_organized_copy(self._results(), source, [Path("node_modules")])

        after = sorted(str(p.relative_to(source)) for p in source.rglob("*"))
        assert before == after

    def test_passthrough_inside_project_travels_with_project(self, tmp_path):
        """A passthrough dir nested inside a project root must not be copied
        separately - it travels with the project as one unit."""
        source = tmp_path / "messy"
        (source / "WeatherApp").mkdir(parents=True)
        (source / "WeatherApp" / "pyproject.toml").write_text("[project]\n")
        (source / "WeatherApp" / "node_modules").mkdir(parents=True)
        (source / "WeatherApp" / "node_modules" / "pkg").mkdir(parents=True)
        (source / "WeatherApp" / "node_modules" / "pkg" / "index.js").write_text("x")

        results = [
            {
                "type": "project",
                "path": "WeatherApp",
                "suggested_folder": "Programming",
            },
        ]

        new_folder, stats = create_organized_copy(
            results, source, [Path("WeatherApp/node_modules")]
        )

        assert (new_folder / "Programming/WeatherApp/node_modules/pkg/index.js").is_file()
        assert stats["passthrough_copied"] == 0
        assert stats["errors"] == 0

    def test_missing_source_is_an_error_not_a_crash(self, tmp_path):
        source = tmp_path / "messy"
        self._make_source(source)

        results = [
            {
                "type": "file",
                "path": "photos/vacation.jpg",
                "suggested_folder": "Media",
                "suggested_name": "vacation.jpg",
            },
            {
                "type": "file",
                "path": "does/not/exist.txt",
                "suggested_folder": "Media",
                "suggested_name": "missing.txt",
            },
        ]

        new_folder, stats = create_organized_copy(results, source, [])
        assert stats["errors"] == 1
        assert (new_folder / "Media/vacation.jpg").is_file()

    def test_path_escape_in_result_is_an_error(self, tmp_path):
        source = tmp_path / "messy"
        self._make_source(source)

        results = [
            {
                "type": "file",
                "path": "../outside.txt",
                "suggested_folder": "Media",
                "suggested_name": "x.txt",
            },
            {
                "type": "file",
                "path": "photos/vacation.jpg",
                "suggested_folder": "../evil",
                "suggested_name": "vacation.jpg",
            },
        ]

        new_folder, stats = create_organized_copy(results, source, [])
        assert stats["errors"] == 2
        # Nothing escaped the organized folder.
        assert (tmp_path / "evil").exists() is False


class TestVerifyCompleteCopy:
    def test_complete_copy_passes(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "a.txt").write_text("aaa")
        (src / "b.txt").write_text("bbb")
        (dst / "renamed.txt").write_text("aaa")  # renamed, same content
        (dst / "b.txt").write_text("bbb")

        assert verify_complete_copy(src, dst) == []

    def test_missing_file_detected(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "a.txt").write_text("aaa")
        (src / "lost.bin").write_bytes(b"data")
        (dst / "a.txt").write_text("aaa")

        missing = verify_complete_copy(src, dst)
        assert len(missing) == 1
        assert missing[0].endswith("lost.bin")

    def test_hash_file(self, tmp_path):
        p = tmp_path / "f.txt"
        p.write_text("hello")
        import hashlib

        expected = hashlib.sha256(b"hello").hexdigest()
        assert _hash_file(p) == expected


class TestApplySameFolder:
    def test_in_place_swap_keeps_all_content(self, tmp_path):
        source = tmp_path / "messy"
        (source / "photos").mkdir(parents=True)
        (source / "photos" / "vacation.jpg").write_bytes(b"jpgdata")
        (source / "readme.txt").write_text("hello")

        results = [
            {
                "type": "file",
                "path": "photos/vacation.jpg",
                "suggested_folder": "Pictures",
                "suggested_name": "vacation.jpg",
            },
            {
                "type": "file",
                "path": "readme.txt",
                "suggested_folder": "Docs",
                "suggested_name": "readme.txt",
            },
        ]

        apply_changes_same_folder(results, source, [])

        # The original folder is now the organized one.
        assert (source / "Pictures/vacation.jpg").read_bytes() == b"jpgdata"
        assert (source / "Docs/readme.txt").read_text() == "hello"
        # No backup left behind.
        assert not (tmp_path / "messy.jishatlas_backup").exists()

    def test_in_place_aborts_if_copy_incomplete(self, tmp_path):
        source = tmp_path / "messy"
        source.mkdir()
        (source / "a.txt").write_text("aaa")
        (source / "keep.bin").write_bytes(b"precious")

        # The AI result omits keep.bin, so the organized copy will not
        # contain it, and the safety check must refuse to touch the original.
        results = [
            {
                "type": "file",
                "path": "a.txt",
                "suggested_folder": "A",
                "suggested_name": "a.txt",
            },
        ]

        apply_changes_same_folder(results, source, [])

        # Original untouched.
        assert (source / "a.txt").read_text() == "aaa"
        assert (source / "keep.bin").read_bytes() == b"precious"

    def test_copy_mode_warns_when_ai_omits_files(self, tmp_path, capsys):
        """If the AI output omits a file, copy mode must not silently declare
        success - it should warn about the missing files."""
        source = tmp_path / "messy"
        source.mkdir()
        (source / "a.txt").write_text("aaa")
        (source / "omitted.bin").write_bytes(b"precious")

        results = [
            {
                "type": "file",
                "path": "a.txt",
                "suggested_folder": "A",
                "suggested_name": "a.txt",
            },
        ]

        apply_changes_diff_folder(results, source, [])

        out = capsys.readouterr().out
        assert "omitted.bin" in out
        assert "1 file(s) were not copied" in out
        # The original folder is untouched in copy mode.
        assert (source / "omitted.bin").read_bytes() == b"precious"

    def test_copy_mode_silent_success_when_complete(self, tmp_path, capsys):
        source = tmp_path / "messy"
        source.mkdir()
        (source / "a.txt").write_text("aaa")

        results = [
            {
                "type": "file",
                "path": "a.txt",
                "suggested_folder": "A",
                "suggested_name": "a.txt",
            },
        ]

        apply_changes_diff_folder(results, source, [])

        out = capsys.readouterr().out
        assert "Organization completed successfully!" in out
        assert "were not copied" not in out
