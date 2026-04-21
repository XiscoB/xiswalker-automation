"""Tests for xiswalker.ocr pure logic functions."""

import pytest

from xiswalker.ocr import fuzzy_ratio, OcrMatchResult


class TestFuzzyRatio:
    def test_exact_match(self):
        assert fuzzy_ratio("OK", "OK") == 1.0

    def test_identical_longer_strings(self):
        assert fuzzy_ratio("Accept", "Accept") == 1.0

    def test_near_match_above_threshold(self):
        # "Accpet" vs "Accept" — one transposition, should be high
        ratio = fuzzy_ratio("Accpet", "Accept")
        assert ratio > 0.8

    def test_completely_different_strings(self):
        ratio = fuzzy_ratio("XYZ", "abc")
        assert ratio < 0.5

    def test_case_sensitive_no_match(self):
        # fuzzy_ratio is case-sensitive by default
        assert fuzzy_ratio("ok", "OK") < 1.0

    def test_case_insensitive_via_lower(self):
        # Callers lower-case both strings for case-insensitive matching
        assert fuzzy_ratio("ok".lower(), "OK".lower()) == 1.0

    def test_empty_strings(self):
        assert fuzzy_ratio("", "") == 1.0

    def test_partial_word(self):
        # Short word contained inside longer — ratio depends on lengths
        ratio = fuzzy_ratio("OK", "OK Button")
        assert 0.0 < ratio < 1.0


class TestOcrMatchResult:
    def test_default_not_found(self):
        r = OcrMatchResult(found=False)
        assert r.found is False
        assert r.x == 0
        assert r.y == 0
        assert r.w == 0
        assert r.h == 0
        assert r.text == ""

    def test_found_fields(self):
        r = OcrMatchResult(found=True, x=100, y=200, w=50, h=20, text="Accept")
        assert r.found is True
        assert r.x == 100
        assert r.y == 200
        assert r.w == 50
        assert r.h == 20
        assert r.text == "Accept"

    def test_center_calculation(self):
        r = OcrMatchResult(found=True, x=100, y=200, w=60, h=20)
        # Center should be x + w//2, y + h//2
        center_x = r.x + r.w // 2
        center_y = r.y + r.h // 2
        assert center_x == 130
        assert center_y == 210
