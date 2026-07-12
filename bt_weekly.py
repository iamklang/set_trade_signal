#!/usr/bin/env python3
"""
bt_weekly.py — 1-week horizon backtest: current V5 vs weekly-tuned variants.

Tests whether faster entry (dip|breakout), tighter stops (5-bar), lower T1 (0.5R),
and time-based exits (5 bars) improve 1-week P/L vs the current let-run system.

Each variant measured two ways:
  natural  — the variant's own exit rule runs to completion
  week-1   — P/L at bar 5 (realised if already exited, mark-to-market if still open)

Usage: python bt_weekly.py [--years 10] [--q1]
NOT advice — mechanics only; SET100 = today's survivors (survivorship-inflated).
"""
import argparse
import sys

import numpy as np
import pandas as pd

HERE = "/Users/klang/Git/trading_dr"
sys.path.insert(0, HERE)
import setdw_signal as sig
import bullish_signals as bull
import composite
import set_data

COST = 0.003
COOLDOWN = 5


def load_universe(path):
    with open(path) as f:
        return [t.split("#")[0].strip() for t in f if t.split("#")[0].strip()]


def prep(df, cfg=None):
    cfg = cfg or {"rsi_min": sig.RSI_MIN, "adx_min": sig.ADX_MIN, "need_vol_conf": True}
    d = bull.add_signals(df, cfg)
    d["buy_dip"] = d["dip"]
    d["buy_dip_or_brk"] = d["dip"] | d["breakout"]
    d["llStop5"] = d["Low"].rolling(5).min()
    return d


VARIANTS = [
    ("V5_run", {
        "entry": "buy_dip", "stop_col": "llStop", "t1_mult": 1.0, "time_exit": None,
        "desc": "current (dip, stop10, T1=1R, trail)",
    }),
    ("V5+fast", {
        "entry": "buy_dip_or_brk", "stop_col": "llStop", "t1_mult": 1.0, "time_exit": None,
        "desc": "faster entry (dip|brk, stop10, T1=1R, trail)",
    }),
    ("V6_dip_wk", {
        "entry": "buy_dip", "stop_col": "llStop5", "t1_mult": 0.5, "time_exit": 5,
        "desc": "weekly exit (dip, stop5, T1=0.5R, 5-bar exit)",
    }),
    ("V6_weekly", {
        "entry": "buy_dip_or_brk", "stop_col": "llStop5", "t1_mult": 0.5, "time_exit": 5,
        "desc": "weekly combo (dip|brk, stop5, T1=0.5R, 5-bar exit)",
    }),
]


def sim_trade(df, i, vcfg):
    """Simulate one trade from bar i. Returns dict with ret, w1_ret, bars, reason or None."""
    c = df["Close"].values
    h = df["High"].values
    l = df["Low"].values
    o = df["Open"].values
    ema = df["ema"].values
    n = len(df)

    entry = c[i]
    stop = df[vcfg["stop_col"]].values[i]
    if not (entry > stop > 0):
        return None

    risk = entry - stop
    t1 = entry + vcfg["t1_mult"] * risk
    time_exit = vcfg["time_exit"]
    t1_hit = False
    cur_stop = stop
    nat_ret, nat_bars, nat_reason = None, None, None

    for j in range(i + 1, n):
        bars = j - i

        if l[j] <= cur_stop:
            fill = min(o[j], cur_stop)
            nat_ret = (fill - entry) / entry
            nat_bars = bars
            nat_reason = "BE" if t1_hit else "STOP"
            break

        if not t1_hit and h[j] >= t1:
            t1_hit = True
            cur_stop = entry

        if t1_hit and c[j] < ema[j]:
            nat_ret = (c[j] - entry) / entry
            nat_bars = bars
            nat_reason = "TRAIL"
            break

        if time_exit and bars >= time_exit:
            nat_ret = (c[j] - entry) / entry
            nat_bars = bars
            nat_reason = "TIME"
            break

    if nat_ret is None:
        nat_ret = (c[-1] - entry) / entry
        nat_bars = n - 1 - i
        nat_reason = "EOD"

    w1_ret = None
    if nat_bars <= 5:
        w1_ret = nat_ret
    elif i + 5 < n:
        w1_ret = (c[i + 5] - entry) / entry

    return {"ret": nat_ret, "w1": w1_ret, "bars": nat_bars, "reason": nat_reason}


def run_variant(frames, vcfg, q1map=None):
    trades = []
    entry_col = vcfg["entry"]
    for t, df in frames.items():
        buy = df[entry_col].values
        idx = df.index
        i = 0; n = len(df)
        last_exit = -10_000
        while i < n:
            if buy[i] and (i - last_exit) >= COOLDOWN:
                if q1map is not None:
                    ms = [m for m in q1map if m <= idx[i]]
                    if not ms or t not in q1map[max(ms)]:
                        i += 1; continue
                res = sim_trade(df, i, vcfg)
                if res is None:
                    i += 1; continue
                res["ret"] -= 2 * COST
                if res["w1"] is not None:
                    res["w1"] -= 2 * COST
                trades.append(res)
                last_exit = i + res["bars"]
                i = last_exit + 1
            else:
                i += 1
    return trades


def pf(rets):
    w = rets[rets > 0].sum()
    l = -rets[rets < 0].sum()
    return w / l if l > 0 else np.inf


def print_table(title, frames, q1map=None):
    print(f"\n{title}")
    hdr = (f"  {'variant':<12s}{'n':>6s}{'win%':>7s}{'avg%':>7s}{'med%':>7s}"
           f"{'PF':>6s}{'hold':>5s}"
           f"  │{'w1 n':>6s}{'w1win':>6s}{'w1avg':>7s}{'w1PF':>6s}")
    print(hdr)
    print("  " + "─" * 74)

    for name, vcfg in VARIANTS:
        trades = run_variant(frames, vcfg, q1map)
        if not trades:
            print(f"  {name:<12s}  (no trades)")
            continue

        rets = np.array([t["ret"] for t in trades])
        bars = np.array([t["bars"] for t in trades])
        w1 = np.array([t["w1"] for t in trades if t["w1"] is not None])

        w1n = len(w1)
        w1_win = (w1 > 0).mean() * 100 if w1n else 0
        w1_avg = w1.mean() * 100 if w1n else 0
        w1_pf = pf(w1) if w1n else 0

        print(f"  {name:<12s}{len(rets):>6d}{(rets>0).mean()*100:>7.1f}"
              f"{rets.mean()*100:>7.2f}{np.median(rets)*100:>7.2f}"
              f"{pf(rets):>6.2f}{int(np.median(bars)):>5d}"
              f"  │{w1n:>6d}{w1_win:>6.1f}{w1_avg:>7.2f}{w1_pf:>6.2f}")

        reasons = {}
        for t in trades:
            reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
        top = " ".join(f"{k}:{n}" for k, n in sorted(reasons.items(), key=lambda x: -x[1]))
        print(f"  {'':12s}  {vcfg['desc']}")
        print(f"  {'':12s}  exits: {top}")


def q1_monthly(frames):
    px = pd.DataFrame({t: df["Close"] for t, df in frames.items()}).sort_index()
    out = {}
    for d in px.resample("ME").last().index:
        R = composite.cross_section_scores(
            frames, asof=d, weights={"mom": 1, "trend": 1, "lowvol": 0})
        if not R.empty:
            out[d] = set(R[R["quintile"] == 1].index)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--universe", default=f"{HERE}/set100.bk.txt")
    ap.add_argument("--q1", action="store_true",
                    help="also run with Q1 composite filter")
    a = ap.parse_args()

    tickers = load_universe(a.universe)
    print(f"fetching {len(tickers)} names, {a.years}y Yahoo ...")
    raw = set_data.fetch_yahoo_all(tickers, period=f"{a.years}y")
    frames = {}
    for t, df in raw.items():
        if df is None or len(df) < sig.SMA_LEN + 60:
            continue
        frames[t] = prep(df)
    print(f"usable: {len(frames)} names")

    print_table("=== ALL entries (no composite filter) ===", frames)

    if a.q1:
        print("\ncomputing monthly composite Q1 (mom+trend) ...")
        q1map = q1_monthly(frames)
        print_table("=== Q1-leaders-only ===", frames, q1map)

    print("\nlegend: natural exit stats │ week-1 (day-5) P/L stats")
    print("  w1 = P/L at bar 5 (realised if already exited, MTM if still open)")
    print("  PF = profit factor (gross wins / gross losses)")


if __name__ == "__main__":
    main()
