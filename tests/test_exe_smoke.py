"""Smoke tests for the packaged JishAtlas.exe.

These are the only tests that exercise the PyInstaller bundle itself. They
catch packaging failures (e.g. missing ctypes-loaded llama_cpp DLLs or
google.genai submodules) that unit tests cannot, because the unit tests run
against the venv where those packages are installed normally.

To build the exe first:

    pyinstaller JishAtlas.spec

These tests skip automatically when dist/JishAtlas.exe is absent.
"""

import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXE = PROJECT_ROOT / "dist" / "JishAtlas.exe"
MODEL_FILE = "Qwen3-1.7B-Q4_K_M.gguf"

pytestmark = pytest.mark.skipif(
    not EXE.exists(),
    reason="dist/JishAtlas.exe not built - run: pyinstaller JishAtlas.spec",
)


def _run_exe(answers, timeout=600):
    """Run the packaged exe with newline-separated answers piped to stdin."""
    return subprocess.run(
        [str(EXE)],
        input="\n".join(answers) + "\n",
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )


def _model_available() -> bool:
    app_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "JishAtlas"
    return (app_dir / "models" / MODEL_FILE).is_file()


class TestExeStartup:
    def test_nonexistent_folder_handled_gracefully(self, tmp_path):
        """The frozen binary imports every module (llama_cpp, genai, dotenv...)
        and handles invalid input without a traceback."""
        missing = tmp_path / "does_not_exist"
        result = _run_exe([str(missing), "1", "2", "n"], timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Folder does not exist" in result.stdout
        assert "Traceback" not in result.stdout + result.stderr


class TestExeFullFlow:
    def test_full_organize_flow(self, tmp_path):
        """End-to-end: scan -> local AI -> organized copy, exit 0, and every
        original file present in the output. Requires the downloaded local
        model (skipped otherwise - first run downloads it automatically)."""
        if not _model_available():
            pytest.skip("Local model not downloaded yet - full AI flow requires it")

        source = tmp_path / "messy"
        (source / "photos").mkdir(parents=True)
        (source / "photos" / "vacation.jpg").write_bytes(b"jpgdata")
        (source / "notes.txt").write_text("some notes")
        (source / "node_modules").mkdir(parents=True)
        (source / "node_modules" / "pkg").mkdir()
        (source / "node_modules" / "pkg" / "index.js").write_text("x")

        result = _run_exe([str(source), "1", "2", "y"])

        assert result.returncode == 0, result.stdout + result.stderr
        # The local model is non-deterministic and may omit a file on some
        # runs, in which case the summary warns instead of saying "completed
        # successfully". Assert on the stable parts of the output.
        assert "Files organized" in result.stdout
        assert "Traceback" not in result.stdout + result.stderr

        organised = source.with_name(source.name + "_Organised")
        assert organised.is_dir()

        # Every original file is present in the organized copy (by name).
        original = {p.name for p in source.rglob("*") if p.is_file()}
        copied = {p.name for p in organised.rglob("*") if p.is_file()}
        assert original <= copied
