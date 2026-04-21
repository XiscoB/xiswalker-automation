"""Tests for xiswalker.timer_parser pure logic functions."""

import pytest

from xiswalker.timer_parser import (
    parse_timer_seconds,
    find_timer_in_text,
    extract_timer_seconds,
    format_seconds,
)


class TestParseTimerSeconds:
    # Basic textual formats
    def test_1h_21min_with_dots(self):
        assert parse_timer_seconds("1h. 21min.") == 4860

    def test_1h_21min_no_dots(self):
        assert parse_timer_seconds("1h 21min") == 4860

    def test_45min(self):
        assert parse_timer_seconds("45min") == 2700

    def test_45_minutes(self):
        assert parse_timer_seconds("45 minutes") == 2700

    def test_2h(self):
        assert parse_timer_seconds("2h") == 7200

    def test_2_hours(self):
        assert parse_timer_seconds("2 hours") == 7200

    def test_30s(self):
        assert parse_timer_seconds("30s") == 30

    def test_30_seconds(self):
        assert parse_timer_seconds("30 seconds") == 30

    def test_30_sec(self):
        assert parse_timer_seconds("30sec") == 30

    def test_1h_21min_30s(self):
        assert parse_timer_seconds("1h 21min 30s") == 4890  # 3600 + 1260 + 30

    def test_zero_minutes(self):
        assert parse_timer_seconds("0min") == 0

    def test_no_match(self):
        assert parse_timer_seconds("hello world") is None

    def test_no_match_empty(self):
        assert parse_timer_seconds("") is None

    # Clock formats
    def test_clock_hms(self):
        assert parse_timer_seconds("01:21:30") == 4890

    def test_clock_ms(self):
        assert parse_timer_seconds("21:30") == 1290

    def test_clock_h_mm_ss(self):
        assert parse_timer_seconds("2:00:00") == 7200

    def test_clock_zero(self):
        assert parse_timer_seconds("00:00") == 0


class TestFindTimerInText:
    def test_finds_1h_21min_in_sentence(self):
        blob = "Crafting complete in 1h. 21min. Click to collect."
        result = find_timer_in_text(blob)
        assert result is not None
        assert parse_timer_seconds(result) == 4860  # 3600 + 1260

    def test_finds_minutes_only_in_sentence(self):
        blob = "Ready in 45min!"
        result = find_timer_in_text(blob)
        assert result is not None
        assert parse_timer_seconds(result) == 2700

    def test_finds_clock_in_sentence(self):
        blob = "Time remaining: 01:21:30"
        result = find_timer_in_text(blob)
        assert result is not None
        assert parse_timer_seconds(result) == 4890

    def test_finds_2h_in_sentence(self):
        blob = "Wait 2h before the next craft."
        result = find_timer_in_text(blob)
        assert result is not None
        assert parse_timer_seconds(result) == 7200

    def test_no_timer_in_blob(self):
        assert find_timer_in_text("No timer here, just regular text.") is None

    def test_empty_blob(self):
        assert find_timer_in_text("") is None


class TestExtractTimerSeconds:
    def test_sentence_with_timer(self):
        assert extract_timer_seconds("Ready in 45min!") == 2700

    def test_sentence_with_h_min(self):
        assert extract_timer_seconds("Crafting: 1h 21min remaining") == 4860  # 3600 + 1260

    def test_no_timer(self):
        assert extract_timer_seconds("No timer here") is None

    def test_clock_in_blob(self):
        assert extract_timer_seconds("Time left: 00:30") == 30


class TestFormatSeconds:
    def test_hours_minutes_seconds(self):
        assert format_seconds(4950) == "1h 22m 30s"

    def test_minutes_seconds(self):
        assert format_seconds(150) == "2m 30s"

    def test_seconds_only(self):
        assert format_seconds(45) == "45s"

    def test_zero(self):
        assert format_seconds(0) == "0s"

    def test_exact_hour(self):
        assert format_seconds(3600) == "1h 0m 0s"
