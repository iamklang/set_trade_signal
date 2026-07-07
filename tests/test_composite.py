"""Tests for composite.py — cross-sectional multi-factor ranking."""
import numpy as np
import pandas as pd

import composite


def _series(n, drift, vol, seed):
    """A synthetic price path: geometric random walk with a given drift/vol."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    px = 100 * np.exp(np.cumsum(rets))
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame({"Open": px, "High": px, "Low": px, "Close": px,
                         "Volume": 1_000_000}, index=idx)


def test_raw_factors_none_when_short():
    assert composite.raw_factors(_series(50, 0.0005, 0.01, 1)) is None


def test_raw_factors_fields():
    rf = composite.raw_factors(_series(400, 0.0008, 0.012, 2))
    assert set(rf) == {"mom", "trend", "lowvol"}
    assert rf["lowvol"] < 0            # stored as -vol (higher = calmer)


def test_quality_hook_passthrough():
    rf = composite.raw_factors(_series(400, 0.0005, 0.01, 3), quality=0.25)
    assert rf["quality"] == 0.25


def test_ranking_puts_strong_trend_on_top():
    """Higher drift + lower vol should score a better (lower) rank."""
    # very low vol so 12-1 momentum (measured at two endpoints) tracks drift, not the
    # accumulated endpoint noise — makes the drift ordering deterministic.
    frames = {
        "STRONG": _series(400, 0.0020, 0.0003, 10),   # highest drift -> best
        "OK": _series(400, 0.0010, 0.0005, 14),
        "MID": _series(400, 0.0005, 0.0008, 11),
        "FLAT": _series(400, 0.0000, 0.0010, 13),
        "WEAK": _series(400, -0.0010, 0.0015, 12),    # falling -> worst
    }
    R = composite.cross_section_scores(frames)
    assert not R.empty
    assert R.iloc[0].name == "STRONG"                # best composite first
    assert R.loc["STRONG", "rank"] < R.loc["WEAK", "rank"]
    assert set(R["quintile"].unique()) <= {1, 2, 3, 4, 5}
    # composite is the mean of the z-scores actually used
    zcols = [c for c in R.columns if c.startswith("z_")]
    assert np.allclose(R["composite"], R[zcols].mean(axis=1), atol=1e-9)


def test_empty_when_too_few_names():
    assert composite.cross_section_scores({"A": _series(400, 0.001, 0.01, 1)}).empty


def _flat_frames():
    """5 near-identical calm risers so mom/trend barely differ — lets a quality tilt dominate."""
    return {k: _series(400, 0.0008, 0.0004, i) for i, k in enumerate("ABCDE")}


def test_quality_factor_ranks_by_roe():
    quality = {"A": 5.0, "B": 30.0, "C": 10.0, "D": 20.0, "E": 1.0}   # B best, E worst
    R = composite.cross_section_scores(
        _flat_frames(), weights={"mom": 0, "trend": 0, "lowvol": 0, "quality": 1},
        quality=quality)
    assert not R.empty
    assert R.iloc[0].name == "B" and R.iloc[-1].name == "E"


def test_partial_quality_imputes_neutral_not_dropped():
    """Names missing ROE get z=0 (neutral) — the factor still blends, nothing is dropped."""
    quality = {"A": 25.0, "B": None, "C": 5.0, "D": None, "E": 15.0}
    R = composite.cross_section_scores(
        _flat_frames(), weights={"mom": 1, "trend": 1, "lowvol": 0, "quality": 1},
        quality=quality)
    assert len(R) == 5                       # all names kept
    assert "z_quality" in R.columns          # quality still contributed
    assert R.loc["B", "z_quality"] == 0.0    # missing -> neutral
