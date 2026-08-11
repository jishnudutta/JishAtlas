"""Unit tests for input.py (non-interactive helpers only)."""

from pathlib import Path

from input import get_app_dir


class TestGetAppDir:
    def test_uses_localappdata(self, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", "C:/Custom/AppData")
        assert get_app_dir() == Path("C:/Custom/AppData/JishAtlas")

    def test_falls_back_to_home(self, monkeypatch):
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.setenv("USERPROFILE", "C:/Users/Someone")
        # On Windows, Path.home() reads USERPROFILE.
        assert get_app_dir() == Path("C:/Users/Someone/JishAtlas")
