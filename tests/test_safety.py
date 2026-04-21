"""Tests for xiswalker.safety — Testing pure functions only.

As per AGENTS.md, we do NOT test OS interaction (win32gui) or hardware
simulation (pynput) directly. We test ONLY business logic like humanization 
variance math and window title string matching.
"""

from xiswalker.safety import match_window_title, apply_humanization, apply_mouse_jitter, parse_key_combo


class TestMatchWindowTitle:
    """Test window title pattern matching."""

    def test_exact_match(self):
        assert match_window_title("MyApp", ["MyApp"]) is True

    def test_case_insensitivity(self):
        assert match_window_title("myapp", ["MyApp"]) is True
        assert match_window_title("MYAPP", ["myapp"]) is True

    def test_substring_match(self):
        assert match_window_title("MyApp - UserSession", ["MyApp"]) is True
        assert match_window_title("Special [XW] Client", ["XW"]) is True

    def test_no_match(self):
        assert match_window_title("Notepad", ["MyApp", "XW"]) is False

    def test_empty_patterns(self):
        # Empty patterns mean nothing matches unless explicitly handled beforehand
        assert match_window_title("MyApp", []) is False


class TestApplyHumanization:
    """Test the delay variance calculation."""

    def test_zero_variance(self):
        assert apply_humanization(1.0, 0.0) == 1.0

    def test_never_negative(self):
        assert apply_humanization(-1.0, 0.0) == 0.0
        assert apply_humanization(0.0, 0.1) == 0.0

    def test_within_bounds(self):
        delay = 10.0
        variance = 0.05  # +/- 5% max variance (0.5 bounds)
        
        # Test 100 times to ensure strict boundary adherence
        for _ in range(100):
            result = apply_humanization(delay, variance)
            assert 9.5 <= result <= 10.5


class TestApplyMouseJitter:
    """Test structural jitter on mouse coords."""

    def test_zero_jitter(self):
        assert apply_mouse_jitter(100, 0) == 100

    def test_within_bounds(self):
        for _ in range(100):
            result = apply_mouse_jitter(500, 2)
            assert 498 <= result <= 502


class TestParseKeyCombo:
    """Test key combination string parsing."""

    def test_single_key(self):
        assert parse_key_combo("esc") == "<esc>"
        assert parse_key_combo("f1") == "<f1>"
        assert parse_key_combo("end") == "<end>"

    def test_simple_combo(self):
        assert parse_key_combo("ctrl+shift+end") == "<ctrl>+<shift>+<end>"
        assert parse_key_combo("ctrl+f12") == "<ctrl>+<f12>"

    def test_case_insensitive(self):
        assert parse_key_combo("CTRL+SHIFT+END") == "<ctrl>+<shift>+<end>"
        assert parse_key_combo("Esc") == "<esc>"

    def test_whitespace_handling(self):
        assert parse_key_combo("ctrl + shift + end") == "<ctrl>+<shift>+<end>"

    def test_special_key_aliases(self):
        assert parse_key_combo("escape") == "<esc>"  # alias
        assert parse_key_combo("return") == "<enter>"  # alias
        assert parse_key_combo("del") == "<delete>"  # alias
