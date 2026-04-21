"""Tests for xiswalker.config — Testing pure configuration logic.

As per AGENTS.md, we test ONLY pure functions like configuration 
validation and data structure logic.
"""

from xiswalker.config import InputConfig, SafetyConfig


class TestInputConfig:
    """Test InputConfig dataclass defaults and structure."""

    def test_default_recording_stop_key(self):
        cfg = InputConfig()
        assert cfg.recording_stop_key == "esc"

    def test_default_playback_stop_key(self):
        cfg = InputConfig()
        assert cfg.playback_stop_key == "ctrl+shift+end"

    def test_default_show_overlay(self):
        cfg = InputConfig()
        assert cfg.show_overlay is True

    def test_custom_values(self):
        cfg = InputConfig(
            recording_stop_key="f12",
            playback_stop_key="ctrl+alt+s",
            show_overlay=False
        )
        assert cfg.recording_stop_key == "f12"
        assert cfg.playback_stop_key == "ctrl+alt+s"
        assert cfg.show_overlay is False


class TestSafetyConfig:
    """Test SafetyConfig dataclass defaults and structure."""

    def test_default_check_window_focus(self):
        cfg = SafetyConfig()
        assert cfg.check_window_focus is True

    def test_default_window_patterns(self):
        cfg = SafetyConfig()
        assert "XisWalker" in cfg.window_patterns
        assert "cmd" in cfg.window_patterns

    def test_custom_window_patterns(self):
        cfg = SafetyConfig(window_patterns=["MyGame", "Test"])
        assert cfg.window_patterns == ["MyGame", "Test"]
