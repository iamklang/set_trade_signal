"""
bullish_signals.py — broad EOD "bullish / buy" signal set for a SET universe.

Where setdw_signal.buy_signal is ONE narrow entry (buy the fresh dip to EMA), this widens
the net to the family of bullish triggers the user asked to scan for, all evaluated on the
just-closed daily bar and all built on setdw_signal.add_indicators so they stay consistent:

  trend     confirmed uptrend  : close>EMA20 & EMA20 rising & EMA20>SMA200 & SMA200 rising
  breakout  N-day-high breakout: close breaks the prior BREAKOUT_LOOK-day high, in uptrend,
                                 with volume>average (a fresh continuation break)
  reclaim   pullback-then-bounce: in an uptrend, close crosses back ABOVE EMA20 from at/below
  golden    trend birth        : EMA20 crosses above SMA200 (fires only on the crossover bar)
  dip       the strict swing dip: setdw_signal.buy_signal (kept as the highest-quality tag)

`bull` = OR of all of the above. `trend` is deliberately broad (status, not a trigger) — filter
to breakout/reclaim/golden/dip when you want actionable entries only.
"""
import setdw_signal as sig

BREAKOUT_LOOK = 20          # prior-high lookback for the breakout trigger

# order = display/priority order (most actionable first, trend/status last)
SIGNAL_COLS = ["dip", "breakout", "reclaim", "golden", "trend"]


def add_signals(df, cfg=None):
    """Attach indicators + boolean signal columns (SIGNAL_COLS) + `bull` (any) to df.
    Expects OHLCV columns; returns the same df with columns added."""
    d = sig.add_indicators(df)
    c, h = d["Close"], d["High"]
    trend = (c > d["ema"]) & d["emaUp"] & (d["ema"] > d["sma"]) & d["smaUp"]
    prior_high = h.rolling(BREAKOUT_LOOK).max().shift(1)
    d["trend"] = trend
    d["breakout"] = trend & (c > prior_high) & (d["Volume"] > d["volSma"])
    d["reclaim"] = trend & (c > d["ema"]) & (c.shift(1) <= d["ema"].shift(1))
    d["golden"] = (d["ema"] > d["sma"]) & (d["ema"].shift(1) <= d["sma"].shift(1))
    d["dip"] = sig.buy_signal(d, cfg)
    d["bull"] = d[SIGNAL_COLS].any(axis=1)
    return d


def fired_on_row(row):
    """List of signal names (SIGNAL_COLS order) that are True on a given df row."""
    return [s for s in SIGNAL_COLS if bool(row.get(s))]
