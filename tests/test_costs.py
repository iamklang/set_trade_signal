"""Tests for costs.py — the SET tick-size transaction-cost model + liquidity helpers."""
import pandas as pd

import costs


def test_spread_ticks_buckets():
    assert costs.spread_ticks_for(200e6) == 0.5     # very liquid
    assert costs.spread_ticks_for(50e6) == 1.0
    assert costs.spread_ticks_for(10e6) == 1.5
    assert costs.spread_ticks_for(1e6) == 2.0       # thin -> wide -> edge-killer
    assert costs.spread_ticks_for(float("nan")) == 1.5
    assert costs.spread_ticks_for(None) == 1.5


def _df(close, vol, n=30):
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": [close] * n, "High": [close] * n, "Low": [close] * n,
                         "Close": [close] * n, "Volume": [vol] * n}, index=idx)


def test_trailing_turnover_value():
    # close 10 × vol 3M = ฿30M/day
    tv = costs.trailing_turnover(_df(10.0, 3_000_000))
    assert tv == 30_000_000


def test_trailing_turnover_short_frame_is_none():
    assert costs.trailing_turnover(_df(10.0, 1e6, n=5)) is None
    assert costs.trailing_turnover(None) is None


def test_tick_table_bands():
    assert costs.set_tick(1.5) == 0.01
    assert costs.set_tick(4) == 0.02
    assert costs.set_tick(9) == 0.05
    assert costs.set_tick(20) == 0.10
    assert costs.set_tick(40) == 0.25
    assert costs.set_tick(150) == 0.50
    assert costs.set_tick(300) == 1.00
    assert costs.set_tick(500) == 2.00


def test_tick_band_boundaries_are_exclusive_upper():
    assert costs.set_tick(2.0) == 0.02      # 2.0 falls into the 2-5 band, not the <2 band
    assert costs.set_tick(100.0) == 0.50    # 100 -> 100-200 band


def test_half_spread_is_half_a_tick_over_price():
    assert costs.half_spread_frac(20.0, spread_ticks=1.0) == 0.5 * 0.10 / 20.0
    # thin name quoting 2 ticks pays double
    assert costs.half_spread_frac(20.0, spread_ticks=2.0) == 0.5 * 0.20 / 20.0


def test_side_cost_adds_commission():
    p = 40.0
    assert costs.side_cost(p) == costs.COMMISSION + costs.half_spread_frac(p, 1.0)


def test_spread_ticks_zero_is_commission_only():
    assert costs.side_cost(50.0, spread_ticks=0) == costs.COMMISSION


def test_realistic_cost_exceeds_flat_30bps_for_most_prices():
    # The whole point: flat 0.3%/side is optimistic on the SET tick grid.
    assert costs.side_cost(20.0) > 0.003
    assert costs.side_cost(4.0) > 0.003


def test_zero_or_negative_price_is_safe():
    assert costs.half_spread_frac(0) == 0.0
    assert costs.half_spread_frac(-5) == 0.0
