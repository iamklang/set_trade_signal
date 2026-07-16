"""Tests for the composite-quintile position-size tilt (setdw_signal.size_mult_for /
apply_size_tilt) — validated by bt_portfolio.py to beat equal-weight."""
import json
import time

import pandas as pd

import setdw_signal as sig


def test_size_mult_for_tiers():
    assert sig.size_mult_for(1) == 1.5
    assert sig.size_mult_for(2) == 1.25
    assert sig.size_mult_for(3) == 1.0
    assert sig.size_mult_for(4) == 0.75
    assert sig.size_mult_for(5) == 0.5


def test_size_mult_for_unknown_is_neutral():
    for q in (None, 0, 6, "x", float("nan")):
        assert sig.size_mult_for(q) == 1.0


def test_apply_size_tilt_oversizes_q1():
    plan = {"size": 1000, "close": 10.0}
    sig.apply_size_tilt(plan, 1)
    assert plan["size"] == 1500
    assert plan["size_base"] == 1000
    assert plan["size_mult"] == 1.5
    assert plan["quintile"] == 1


def test_apply_size_tilt_undersizes_q5():
    plan = {"size": 1000}
    sig.apply_size_tilt(plan, 5)
    assert plan["size"] == 500
    assert plan["size_mult"] == 0.5


def test_apply_size_tilt_neutral_without_quintile():
    plan = {"size": 1000}
    sig.apply_size_tilt(plan, None)
    assert plan["size"] == 1000
    assert plan["size_mult"] == 1.0
    assert plan["quintile"] is None


def test_apply_size_tilt_reapplies_from_base_never_compounds():
    plan = {"size": 1000}
    sig.apply_size_tilt(plan, 1)      # 1000 -> 1500
    sig.apply_size_tilt(plan, 5)      # from base 1000 -> 500, NOT 1500*0.5=750
    assert plan["size"] == 500
    assert plan["size_base"] == 1000


def test_apply_size_tilt_floors():
    plan = {"size": 1001}
    sig.apply_size_tilt(plan, 2)      # 1001 * 1.25 = 1251.25 -> 1251 -> lot 100 -> 1200
    assert plan["size"] == 1200


def test_trade_plan_buy_is_signal_close():
    """The next-day buy price = the signal-bar close (what stop/targets/size are built on)."""
    row = pd.Series({"Close": 10.0, "llStop": 9.0, "ema": 9.8, "rsi": 60, "adx": 25})
    p = sig.trade_plan(row, equity=1_000_000, risk_pct=1.0)
    assert p["buy"] == 10.0 == p["close"]


def test_trade_plan_then_tilt_integration():
    row = pd.Series({"Close": 10.0, "llStop": 9.0, "ema": 9.8, "rsi": 60, "adx": 25})
    p = sig.trade_plan(row, equity=1_000_000, risk_pct=1.0)
    base = p["size"]                  # risk_u=1, 1% of 1e6 -> 10,000 units
    assert base == 10_000
    sig.apply_size_tilt(p, 1)
    assert p["size"] == 15_000 and p["size_base"] == 10_000


def test_regime_brake_halves_size():
    plan = {"size": 1000}
    sig.apply_size_tilt(plan, 1, regime_mult=0.5)   # base 1000 × Q1 1.5 × 0.5 = 750 -> lot 100 -> 700
    assert plan["size"] == 700
    assert plan["regime_mult"] == 0.5


def test_regime_brake_neutral_default():
    plan = {"size": 1000}
    sig.apply_size_tilt(plan, 3)                     # Q3 ×1.0 × regime 1.0
    assert plan["size"] == 1000 and plan["regime_mult"] == 1.0


def _idx_frames(direction):
    """Universe of 3 names all trending `direction` so the equal-weight index sits above
    (up) or below (down) its 200-SMA on the last bar."""
    n = 260
    if direction == "up":
        closes = [10 + 0.05 * i for i in range(n)]           # steady rise -> above SMA
    else:
        closes = [10 + 0.05 * i for i in range(n - 40)] + [15 - 0.2 * i for i in range(40)]
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    df = pd.DataFrame({"Open": closes, "High": closes, "Low": closes,
                       "Close": closes, "Volume": [1e6] * n}, index=idx)
    return {"A.BK": df, "B.BK": df.copy(), "C.BK": df.copy()}


def test_market_regime_risk_on_when_above_sma():
    r = sig.market_regime(_idx_frames("up"))
    assert r["risk_off"] is False and r["factor"] == 1.0


def test_market_regime_risk_off_when_below_sma():
    r = sig.market_regime(_idx_frames("down"))
    assert r["risk_off"] is True and r["factor"] == 0.5


def test_market_regime_short_data_is_risk_on():
    idx = pd.date_range("2026-01-01", periods=30, freq="D")
    df = pd.DataFrame({"Close": [10] * 30}, index=idx)
    r = sig.market_regime({"A.BK": df})
    assert r["risk_off"] is False and r["factor"] == 1.0


# ---- load_market_regime — the freshness-guarded reader alert.py/scan_bull.py share ---------

def test_load_market_regime_missing_file_is_neutral(tmp_path):
    factor, age = sig.load_market_regime(str(tmp_path / "nope.json"))
    assert factor == 1.0 and age is None


def test_load_market_regime_reads_fresh_factor(tmp_path):
    p = tmp_path / "market_regime.json"
    p.write_text(json.dumps({"factor": 0.5}))
    factor, age = sig.load_market_regime(str(p))
    assert factor == 0.5 and age is not None and age < 1


def test_load_market_regime_stale_file_falls_back_neutral(tmp_path):
    p = tmp_path / "market_regime.json"
    p.write_text(json.dumps({"factor": 0.5}))
    old = time.time() - 49 * 3600          # 49h old > default max_age_h=48
    import os
    os.utime(p, (old, old))
    factor, age = sig.load_market_regime(str(p))
    assert factor == 1.0                    # falls back, does NOT trust the stale 0.5
    assert age > 48


def test_load_market_regime_corrupt_file_is_neutral(tmp_path):
    p = tmp_path / "market_regime.json"
    p.write_text("not valid json {{{")
    factor, age = sig.load_market_regime(str(p))
    assert factor == 1.0
