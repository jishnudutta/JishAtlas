"""Unit tests for input.py (non-interactive helpers only)."""

from pathlib import Path

import pytest

from input import (
    ask_run_again,
    get_app_dir,
    get_folder,
)


class TestGetAppDir:
    def test_uses_localappdata(self, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", "C:/Custom/AppData")
        assert get_app_dir() == Path("C:/Custom/AppData/JishAtlas")

    def test_falls_back_to_home(self, monkeypatch):
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.setenv("USERPROFILE", "C:/Users/Someone")
        # On Windows, Path.home() reads USERPROFILE.
        assert get_app_dir() == Path("C:/Users/Someone/JishAtlas")


class TestGetFolderQuit:
    def test_quit_returns_none(self, monkeypatch):
        monkeypatch.setattr("input.Prompt.ask", lambda *a, **k: "q")
        assert get_folder() is None

    def test_quit_returns_none_upper_case(self, monkeypatch):
        monkeypatch.setattr("input.Prompt.ask", lambda *a, **k: "Quit")
        assert get_folder() is None

    def test_valid_folder_returns_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr("input.Prompt.ask", lambda *a, **k: str(tmp_path))
        assert get_folder() == tmp_path


class TestAskRunAgain:
    def test_yes_returns_true(self, monkeypatch):
        monkeypatch.setattr("input.Confirm.ask", lambda *a, **k: True)
        assert ask_run_again() is True

    def test_no_returns_false(self, monkeypatch):
        monkeypatch.setattr("input.Confirm.ask", lambda *a, **k: False)
        assert ask_run_again() is False
