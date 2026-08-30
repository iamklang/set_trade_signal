"""Tests for meta_label.py — Phase 1 of /quant-meta-label.

Covers the two pure primitives (triple-barrier labeling, LdP sample-uniqueness)
and the build_dataset schema/label path with an injected deterministic signal so
the suite stays offline and independent of whether any real dip setup fires.
"""
import numpy as np
import pandas as pd

import meta_label as ml


def _ohlc(highs, lows, closes=None, opens=None, vols=None):
    n = len(highs)
    closes = closes if closes is not None else [(h + l) / 2 for h, l in zip(highs, lows)]
    opens = opens if opens is not None else closes
    vols = vols if vols is not None else [1_000_000] * n
    idx = pd.date_range("2021-01-01", periods=n, freq="B")
    return pd.DataFrame({"Open": opens, "High": highs, "Low": lows,
                         "Close": closes, "Volume": vols}, index=idx)


# ---------------- triple_barrier ----------------

def test_triple_barrier_win_upper_first():
    # stop=90, t1=110; bar 2 spikes to 111 with lows safely above stop
    df = _ohlc(highs=[100, 105, 111, 120], lows=[99, 101, 108, 115])
    label, pos = ml.triple_barrier(df, i=0, stop=90, t1=110, vbar=3)
    assert label == 1 and pos == 2


def test_triple_barrier_stop_first():
    df = _ohlc(highs=[100, 101, 130], lows=[99, 89, 120])   # bar 1 low 89 <= stop 90
    label, pos = ml.triple_barrier(df, i=0, stop=90, t1=110, vbar=2)
    assert label == 0 and pos == 1


def test_triple_barrier_timeout_is_zero():
    df = _ohlc(highs=[100, 101, 102, 103], lows=[99, 100, 101, 102])
    label, pos = ml.triple_barrier(df, i=0, stop=90, t1=110, vbar=2)
    assert label == 0 and pos == 2          # neither barrier within 2 bars -> vertical


def test_triple_barrier_conservative_tie_is_stop():
    # same bar touches BOTH t1 (high 111) and stop (low 89) -> scored as stop
    df = _ohlc(highs=[100, 111], lows=[99, 89])
    label, pos = ml.triple_barrier(df, i=0, stop=90, t1=110, vbar=1)
    assert label == 0 and pos == 1


def test_triple_barrier_no_forward_bar():
    df = _ohlc(highs=[100], lows=[99])
    assert ml.triple_barrier(df, i=0, stop=90, t1=110, vbar=5) == (None, None)


# ---------------- sample_uniqueness ----------------

def test_uniqueness_non_overlapping_is_one():
    w = ml.sample_uniqueness([(1, 3), (5, 7)], n_bars=10)
    assert w == [1.0, 1.0]


def test_uniqueness_full_overlap_is_half():
    w = ml.sample_uniqueness([(2, 5), (2, 5)], n_bars=10)
    assert w == [0.5, 0.5]


def test_uniqueness_partial_overlap_between_zero_and_one():
    # spans (1..4) and (3..6) overlap on bars 3,4
    w = ml.sample_uniqueness([(1, 4), (3, 6)], n_bars=10)
    assert all(0.0 < x < 1.0 for x in w)
    assert w[0] == np.mean([1, 1, 0.5, 0.5])


# ---------------- build_dataset ----------------

def _rising_frame(n=260, seed=7):
    """A long, gently rising path with room for a forward spike we control."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0006, 0.008, n)
    px = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"Open": px, "High": px * 1.004, "Low": px * 0.996,
                       "Close": px, "Volume": 1_000_000},
                      index=pd.date_range("2020-01-01", periods=n, freq="B"))
    return df


def test_build_dataset_schema_and_win_label():
    raw = _rising_frame()
    i0 = 240
    # force a guaranteed WIN: huge spike on the bar after the trigger, lows held up
    raw.iloc[i0 + 1, raw.columns.get_loc("High")] = raw["Close"].iloc[i0] * 5
    for k in range(i0 + 1, i0 + 6):
        raw.iloc[k, raw.columns.get_loc("Low")] = raw["Close"].iloc[i0] * 0.999

    def one_shot(df, cfg):
        m = pd.Series(False, index=df.index)
        m.iloc[i0] = True
        return m

    ds = ml.build_dataset({"AAA": raw}, cfg={"composite": False, "market": 1},
                          signal_fn=one_shot)
    # schema
    for col in ml._META + [c for c in ml.FEATURES if c != "market"]:
        assert col in ds.columns
    assert len(ds) == 1
    r = ds.iloc[0]
    assert r["label"] == 1                     # spike hit +1R first
    assert r["market"] == 1
    assert r["weight"] == 1.0                   # single event -> fully unique
    assert np.isfinite(r["rsi"]) and np.isfinite(r["adx"])
    assert np.isfinite(r["distPct"]) and np.isfinite(r["riskU_pct"])
    assert pd.isna(r["z_mom"])                  # composite disabled -> NaN
    assert r["exit_date"] > r["date"]
    assert r["ret_R"] == 1.0                     # upper-barrier win -> +rr (rr default 1.0)


def test_build_dataset_stop_gives_negative_R():
    raw = _rising_frame()
    i0 = 240
    # force a STOP: next bar's low craters below the structural stop
    raw.iloc[i0 + 1, raw.columns.get_loc("Low")] = raw["Close"].iloc[i0] * 0.5

    def one_shot(df, cfg):
        m = pd.Series(False, index=df.index)
        m.iloc[i0] = True
        return m

    ds = ml.build_dataset({"AAA": raw}, cfg={"composite": False}, signal_fn=one_shot)
    assert ds.iloc[0]["label"] == 0
    assert ds.iloc[0]["ret_R"] == -1.0           # stop-out = -1R


def test_build_dataset_empty_has_columns():
    ds = ml.build_dataset({"AAA": _rising_frame()},
                          cfg={"composite": False},
                          signal_fn=lambda df, cfg: pd.Series(False, index=df.index))
    assert len(ds) == 0
    assert "label" in ds.columns and "weight" in ds.columns
    assert ml.effective_n(ds) == 0.0


def test_build_dataset_skips_short_frames():
    ds = ml.build_dataset({"SHORT": _rising_frame(n=50)},
                          cfg={"composite": False},
                          signal_fn=lambda df, cfg: pd.Series(True, index=df.index))
    assert len(ds) == 0


def _frame_ema(closes, lows, ema):
    n = len(closes)
    idx = pd.date_range("2021-01-01", periods=n, freq="B")
    return pd.DataFrame({"Open": closes, "High": [c * 1.01 for c in closes],
                         "Low": lows, "Close": closes, "Volume": 1_000_000,
                         "ema": ema}, index=idx)


def test_trail_win_runs_then_trails_out():
    # entry 100, stop 90 (1R=10), t1=110. bar1 closes 112 -> arm breakeven;
    # bar2 closes 108 below ema 109 -> trail exit at +0.8R
    df = _frame_ema(closes=[100, 112, 108], lows=[99, 105, 106], ema=[100, 100, 109])
    label, pos, r = ml.let_winners_run_label(df, i=0, stop=90, rr1=1.0)
    assert label == 1 and pos == 2 and abs(r - 0.8) < 1e-9


def test_trail_stop_before_1R_is_minus_one():
    df = _frame_ema(closes=[100, 105, 107], lows=[99, 89, 100], ema=[100, 100, 100])
    label, pos, r = ml.let_winners_run_label(df, i=0, stop=90, rr1=1.0)
    assert label == 0 and pos == 1 and r == -1.0


def test_trail_breakeven_after_1R_is_zero():
    # bar1 arms breakeven (close 111); bar2 low 99 <= entry 100 -> breakeven exit
    df = _frame_ema(closes=[100, 111, 101], lows=[99, 105, 99], ema=[100, 100, 100])
    label, pos, r = ml.let_winners_run_label(df, i=0, stop=90, rr1=1.0)
    assert label == 0 and pos == 2 and r == 0.0


def test_trail_maxhold_marks_to_close():
    # never hits +1R nor stop; maxhold=2 -> mark to close 107 = +0.7R
    df = _frame_ema(closes=[100, 105, 107], lows=[99, 95, 96], ema=[90, 90, 90])
    label, pos, r = ml.let_winners_run_label(df, i=0, stop=90, rr1=1.0, maxhold=2)
    assert label == 1 and pos == 2 and abs(r - 0.7) < 1e-9


def test_build_dataset_trail_mode():
    raw = _rising_frame()
    i0 = 240
    raw.iloc[i0 + 1, raw.columns.get_loc("Close")] = raw["Close"].iloc[i0] * 2   # spike past +1R
    raw.iloc[i0 + 1, raw.columns.get_loc("High")] = raw["Close"].iloc[i0] * 2

    def one_shot(df, cfg):
        m = pd.Series(False, index=df.index)
        m.iloc[i0] = True
        return m

    ds = ml.build_dataset({"AAA": raw}, cfg={"composite": False, "exit": "trail"},
                          signal_fn=one_shot)
    assert len(ds) == 1
    assert "ret_R" in ds.columns and np.isfinite(ds.iloc[0]["ret_R"])


def test_effective_n_sums_weights():
    ds = pd.DataFrame({"weight": [1.0, 0.5, 0.5], "label": [1, 0, 1]})
    assert ml.effective_n(ds) == 2.0
