"""Tests for alert.live_status — the latest-bar 'still holdable?' classifier."""
import pandas as pd

import alert


def _rising_df(n=30, start=10.0, step=0.1):
    """A steadily rising daily frame so the last close sits above its EMA20."""
    closes = [start + step * i for i in range(n)]
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "Open": closes, "High": [c + 0.05 for c in closes],
        "Low": [c - 0.05 for c in closes], "Close": closes,
        "Volume": [1_000_000] * n,
    }, index=idx)


CUR = 10.0 + 0.1 * 29        # last close of the default rising frame = 12.9


def test_hold_requires_above_entry_and_ema():
    df = _rising_df()
    s = alert.live_status(df, entry=12.0, stop=11.0, t1=20.0, t2=21.0)
    assert s["status"] == "HOLD"
    assert s["cur"] == CUR
    assert s["pl_pct"] > 0


def test_above_ema_but_below_entry_is_weak():
    """Trend intact (above EMA20) but still underwater vs entry -> not HOLD."""
    df = _rising_df()
    s = alert.live_status(df, entry=13.5, stop=11.0, t1=20.0, t2=21.0)
    assert s["status"] == "WEAK"
    assert s["pl_pct"] < 0


def test_stop_takes_precedence():
    df = _rising_df()
    s = alert.live_status(df, entry=12.0, stop=13.0, t1=20.0, t2=21.0)
    assert s["status"] == "STOP"


def test_target_hit():
    df = _rising_df()
    s = alert.live_status(df, entry=11.0, stop=10.0, t1=12.5, t2=21.0)
    assert s["status"] == "T1"


def test_insufficient_data():
    s = alert.live_status(_rising_df(n=10), entry=10.0, stop=9.0, t1=12.0, t2=13.0)
    assert s["status"] == "?"
    assert s["cur"] is None
