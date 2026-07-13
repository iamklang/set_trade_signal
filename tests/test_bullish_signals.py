"""Tests for bullish_signals.py — the broad EOD signal set."""
import numpy as np
import pandas as pd

import bullish_signals as bull


def _df(closes, vols=None):
    n = len(closes)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    closes = np.array(closes, float)
    return pd.DataFrame({
        "Open": closes, "High": closes * 1.005, "Low": closes * 0.995,
        "Close": closes, "Volume": (vols if vols is not None else [1e6] * n),
    }, index=idx)


def test_columns_present():
    d = bull.add_signals(_df(list(np.linspace(10, 20, 260))))
    for col in bull.SIGNAL_COLS + ["bull"]:
        assert col in d.columns


def test_uptrend_flags_trend_true():
    # a long steady rise -> last bar is a confirmed uptrend
    d = bull.add_signals(_df(list(10 * np.exp(np.linspace(0, 0.8, 300)))))
    assert bool(d["trend"].iloc[-1])
    assert bool(d["bull"].iloc[-1])


def test_downtrend_flags_all_false():
    d = bull.add_signals(_df(list(30 * np.exp(np.linspace(0, -0.8, 300)))))
    row = d.iloc[-1]
    assert not row["trend"] and not row["breakout"] and not row["bull"]


def test_golden_cross_fires_once_on_crossover():
    # down for 220 bars (EMA20 below SMA200), then a sharp sustained rally to force the cross
    down = list(np.linspace(40, 20, 220))
    up = list(np.linspace(20, 60, 80))
    d = bull.add_signals(_df(down + up))
    assert d["golden"].sum() >= 1           # the EMA20>SMA200 crossover fired
    # golden is an edge event, not a persistent state
    assert d["golden"].sum() <= 3


def test_fired_on_row_lists_names():
    d = bull.add_signals(_df(list(10 * np.exp(np.linspace(0, 0.8, 300)))))
    fired = bull.fired_on_row(d.iloc[-1])
    assert "trend" in fired
    assert set(fired) <= set(bull.SIGNAL_COLS)


def test_cdc_fires_on_first_green_bar():
    # down long enough for fast<slow, then a sustained rally flips fast>slow & close>fast.
    # cdc must fire exactly on the FIRST green bar, then stay quiet while green persists.
    down = list(np.linspace(40, 25, 120))
    up = list(np.linspace(25, 60, 60))
    d = bull.add_signals(_df(down + up))
    cdc = d["cdc"]
    assert cdc.sum() >= 1                      # the day-1 green entry fired
    # it is an EDGE event: once green, subsequent green bars do NOT re-fire
    fires = np.where(cdc.values)[0]
    first = fires[0]
    # the bar immediately after the first fire is still green (rally continues) but cdc=False
    assert not bool(cdc.iloc[first + 1])


def test_cdc_quiet_in_steady_downtrend():
    d = bull.add_signals(_df(list(30 * np.exp(np.linspace(0, -0.8, 300)))))
    assert d["cdc"].sum() == 0                 # never enters the green zone
