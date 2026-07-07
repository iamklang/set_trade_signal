"""Tests for alert.py health helpers (staleness check)."""
import datetime

import pytest

import alert


@pytest.mark.skipif(alert._CAL is None, reason="exchange_calendars/XBKK not available")
class TestExpectedLastSession:
    def test_preopen_returns_prior_session(self):
        # Mon 2026-06-29 08:00 (pre-close) -> last CLOSED session is Fri 2026-06-26
        now = datetime.datetime(2026, 6, 29, 8, 0)
        assert alert.expected_last_session(now) == datetime.date(2026, 6, 26)

    def test_postclose_returns_today(self):
        # Mon 2026-06-29 17:00 (after 16:35 close) -> today's session has closed
        now = datetime.datetime(2026, 6, 29, 17, 0)
        assert alert.expected_last_session(now) == datetime.date(2026, 6, 29)

    def test_midweek_preopen(self):
        now = datetime.datetime(2026, 7, 2, 8, 0)
        assert alert.expected_last_session(now) == datetime.date(2026, 7, 1)
