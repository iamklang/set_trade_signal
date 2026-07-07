#!/usr/bin/env python3
"""
test_signal.py — parity / drift guard for setdw_signal.

`setdw_signal` is the single source of truth that must stay in lock-step with the
.pine indicator/strategy. This test pins its numeric output so a refactor (e.g. the
async fetch-layer rewrite) can't silently change the signal math.

Two layers:
  1. GOLDEN-MASTER — last-bar ema/sma/rsi/adx + buy_signal on a committed fixture
     (tests/fixture_kce.csv) must match recorded values. Guards drift.
  2. SANITY — properties that must hold regardless of the snapshot (guards original
     correctness, not just "same as last time"): SMA200 == mean(last 200 closes),
     RSI in [0,100], EMA20 matches the hand-rolled recursion, one hand-computed
     Wilder-RSI value.

Run:  <venv>/bin/python test_signal.py     # exit 0 = pass, 1 = fail
"""
import os
import sys

import numpy as np
import pandas as pd

import setdw_signal as sig

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "tests", "fixture_kce.csv")
TOL = 1e-6

# Recorded from setdw_signal on tests/fixture_kce.csv (last bar 2026-06-26).
# Regenerate intentionally ONLY when the signal math is meant to change.
GOLDEN = {
    "ema": 37.1863273646,
    "sma": 24.7990000000,
    "rsi": 55.8911779624,
    "adx": 33.2807349337,
    "close": 38.2500000000,
    "buy": False,
}

_failures = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{(' — ' + detail) if detail and not cond else ''}")
    if not cond:
        _failures.append(name)


def wilder_rsi_lastbar(close, n=14):
    """Independent Wilder RSI on a numpy close series (mirrors the textbook
    recurrence, not setdw_signal's pandas ewm) — cross-checks the production calc."""
    d = np.diff(close)
    gain = np.clip(d, 0, None)
    loss = np.clip(-d, 0, None)
    ag = gain[:n].mean()
    al = loss[:n].mean()
    for i in range(n, len(d)):
        ag = (ag * (n - 1) + gain[i]) / n
        al = (al * (n - 1) + loss[i]) / n
    rs = ag / al if al != 0 else np.inf
    return 100 - 100 / (1 + rs)


def main():
    df = pd.read_csv(FIXTURE, index_col=0, parse_dates=True)
    d = sig.add_indicators(df)
    r = d.iloc[-1]
    close = d["Close"].to_numpy()

    print("Golden-master (last bar %s):" % d.index[-1].date())
    for k in ("ema", "sma", "rsi", "adx", "close"):
        val = float(r["Close"] if k == "close" else r[k])
        check(f"golden {k}", abs(val - GOLDEN[k]) < TOL,
              f"got {val:.10f} want {GOLDEN[k]:.10f}")
    check("golden buy_signal", bool(sig.buy_signal(d).iloc[-1]) == GOLDEN["buy"])

    print("Sanity properties:")
    check("SMA200 == mean(last 200 closes)",
          abs(float(r["sma"]) - close[-200:].mean()) < TOL)
    check("RSI in [0,100]", 0.0 <= float(r["rsi"]) <= 100.0)
    # EMA20 hand recursion
    alpha = 2 / (20 + 1)
    ema = close[0]
    for px in close[1:]:
        ema = alpha * px + (1 - alpha) * ema
    check("EMA20 matches hand recursion", abs(ema - float(r["ema"])) < 1e-6,
          f"got {float(r['ema']):.8f} hand {ema:.8f}")
    # Independent Wilder RSI
    hand_rsi = wilder_rsi_lastbar(close, 14)
    check("RSI matches independent Wilder calc", abs(hand_rsi - float(r["rsi"])) < 1e-6,
          f"got {float(r['rsi']):.8f} hand {hand_rsi:.8f}")

    print()
    if _failures:
        print(f"FAILED ({len(_failures)}): {', '.join(_failures)}")
        return 1
    print("All signal parity checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
