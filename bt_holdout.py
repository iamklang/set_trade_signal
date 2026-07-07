#!/usr/bin/env python3
"""
bt_holdout.py — time-split holdout to check the composite weights aren't overfit.

The full-sample bt_composite.py picked mom+trend (1,1,0) AFTER comparing 3 blends on
2014-2026 — that is in-sample selection and risks multiple-testing luck. Honest test:
  1. Split the period into IN-SAMPLE (train) and OUT-OF-SAMPLE (holdout).
  2. On IS only, score a grid of weight blends and PICK the best (by Q1 Sharpe).
  3. Report that IS-winner's OOS performance — plus every blend's IS-vs-OOS side by side,
     so we can see whether the IS ranking survives out of sample.
Also prints the default mom+trend Q1 in BOTH halves (stability), always vs Universe(EW).

Efficiency: download once, precompute each name's raw factors at every month-end, then each
weight blend is just a re-z-score + re-quintile over the cached panel (fast).
Yahoo data (long history). Usage: python bt_holdout.py [--years 12] [--cutoff 2021-01-01]
"""
import argparse
import os
import pickle
import sys

import numpy as np
import pandas as pd
import yfinance as yf

HERE = "/Users/klang/Git/trading_dr"
sys.path.insert(0, HERE)
import composite  # noqa: E402

CACHE = "/private/tmp/claude-501/-Users-klang-Git-trading-dr/e1883bdb-3ed2-41b2-bd5f-cccf9e269bb2/scratchpad/_px_cache.pkl"

GRID = {
    "mom (1,0,0)":        {"mom": 1, "trend": 0, "lowvol": 0},
    "trend (0,1,0)":      {"mom": 0, "trend": 1, "lowvol": 0},
    "mom+trend (1,1,0)":  {"mom": 1, "trend": 1, "lowvol": 0},
    "full (1,1,1)":       {"mom": 1, "trend": 1, "lowvol": 1},
    "momhvy (2,1,0)":     {"mom": 2, "trend": 1, "lowvol": 0},
    "trndhvy (1,2,0)":    {"mom": 1, "trend": 2, "lowvol": 0},
    "mt+vol½ (1,1,.5)":   {"mom": 1, "trend": 1, "lowvol": 0.5},
}


def load_universe(path):
    with open(path) as f:
        return [t.split("#")[0].strip() for t in f if t.split("#")[0].strip()]


def fetch(tickers, years):
    key = f"{years}:{','.join(sorted(tickers))}"
    if os.path.exists(CACHE):
        blob = pickle.load(open(CACHE, "rb"))
        if blob.get("key") == key:
            print("  (using cached prices)")
            return blob["frames"], blob["px"]
    frames, closes = {}, {}
    for i, t in enumerate(tickers):
        try:
            df = yf.download(t, period=f"{years}y", interval="1d",
                             progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df is None or len(df) < composite.MIN_BARS:
                continue
            frames[t], closes[t] = df, df["Close"]
        except Exception:
            pass
        if (i + 1) % 25 == 0:
            print(f"  fetched {i + 1}/{len(tickers)} ...")
    px = pd.DataFrame(closes).sort_index()
    pickle.dump({"key": key, "frames": frames, "px": px}, open(CACHE, "wb"))
    return frames, px


def build_panel(frames, me):
    """panel[d0] = DataFrame(index=ticker, cols=mom,trend,lowvol,fwd) — raw factors at d0
    and the forward return over [d0, next month-end]. Computed ONCE, reused per weight."""
    dates = me.index
    panel = {}
    for i in range(len(dates) - 1):
        d0, d1 = dates[i], dates[i + 1]
        rows = {}
        for t, df in frames.items():
            rf = composite.raw_factors(df[df.index <= d0])
            if rf is None:
                continue
            p0, p1 = me.at[d0, t], me.at[d1, t]
            if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
                continue
            rf["fwd"] = p1 / p0 - 1.0
            rows[t] = rf
        if len(rows) >= 20:
            panel[d0] = pd.DataFrame(rows).T.astype(float)
    return panel


def sim(panel, weights):
    """Return (q1..q5 monthly-return Series indexed by d0, universe Series)."""
    q = {i: {} for i in range(1, 6)}
    uni = {}
    for d0, P in panel.items():
        comp = pd.Series(0.0, index=P.index)
        den = 0.0
        for f, w in weights.items():
            if not w:
                continue
            mu, sd = P[f].mean(), P[f].std()
            comp = comp + ((P[f] - mu) / sd if sd > 0 else 0.0) * w
            den += abs(w)
        P = P.assign(composite=comp / den).sort_values("composite", ascending=False)
        n = len(P)
        quint = (np.arange(n) * 5 // n) + 1
        for qi in range(1, 6):
            sub = P["fwd"].values[quint == qi]
            if len(sub):
                q[qi][d0] = float(np.mean(sub))
        uni[d0] = float(P["fwd"].mean())
    return {i: pd.Series(q[i]).sort_index() for i in range(1, 6)}, pd.Series(uni).sort_index()


def stats(r):
    r = r.dropna()
    if len(r) < 6:
        return np.nan, np.nan
    cagr = (1 + r).prod() ** (12 / len(r)) - 1
    sharpe = r.mean() / r.std() * np.sqrt(12) if r.std() > 0 else np.nan
    return cagr, sharpe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=12)
    ap.add_argument("--universe", default=os.path.join(HERE, "set100.bk.txt"))
    ap.add_argument("--cutoff", default="2021-01-01", help="IS/OOS split date")
    a = ap.parse_args()

    tickers = load_universe(a.universe)
    print(f"Holdout test | SET100 {len(tickers)} names | {a.years}y | IS<{a.cutoff}<=OOS\n")
    frames, px = fetch(tickers, a.years)
    me = px.resample("ME").last()
    panel = build_panel(frames, me)
    cut = pd.Timestamp(a.cutoff)
    is_dates = [d for d in panel if d < cut]
    oos_dates = [d for d in panel if d >= cut]
    print(f"  usable {len(frames)} names | IS {len(is_dates)}mo "
          f"({min(is_dates).date()}..{max(is_dates).date()}) | "
          f"OOS {len(oos_dates)}mo ({min(oos_dates).date()}..{max(oos_dates).date()})\n")

    def split(s):
        return s[s.index < cut], s[s.index >= cut]

    print("=" * 86)
    print(f"{'blend':<20}{'IS Q1 CAGR':>12}{'IS Shrp':>9}{'IS exc':>8}   "
          f"{'OOS Q1 CAGR':>12}{'OOS Shrp':>9}{'OOS exc':>8}")
    print("-" * 86)
    rows = {}
    for name, w in GRID.items():
        qser, uni = sim(panel, w)
        q1_is, q1_oos = split(qser[1])
        u_is, u_oos = split(uni)
        isc, iss = stats(q1_is); osc, oss = stats(q1_oos)
        is_exc = isc - stats(u_is)[0]
        oos_exc = osc - stats(u_oos)[0]
        rows[name] = dict(iss=iss, isc=isc, is_exc=is_exc, osc=osc, oss=oss, oos_exc=oos_exc)
        print(f"{name:<20}{isc*100:>11.1f}%{iss:>9.2f}{is_exc*100:>+7.1f}%   "
              f"{osc*100:>11.1f}%{oss:>9.2f}{oos_exc*100:>+7.1f}%")
    print("=" * 86)

    # Universe baseline both halves
    _, uni = sim(panel, GRID["mom+trend (1,1,0)"])
    u_is, u_oos = split(uni)
    print(f"{'Universe(EW)':<20}{stats(u_is)[0]*100:>11.1f}%{stats(u_is)[1]:>9.2f}"
          f"{'—':>8}   {stats(u_oos)[0]*100:>11.1f}%{stats(u_oos)[1]:>9.2f}{'—':>8}")

    # Pick IS-winner by Q1 Sharpe, then reveal its OOS
    win = max(rows, key=lambda k: (rows[k]["iss"] if not np.isnan(rows[k]["iss"]) else -9))
    w = rows[win]
    print(f"\nIS-selected winner (by Q1 Sharpe): **{win}**")
    print(f"  IS : Q1 CAGR {w['isc']*100:.1f}%  Sharpe {w['iss']:.2f}  excess {w['is_exc']*100:+.1f}%/yr")
    print(f"  OOS: Q1 CAGR {w['osc']*100:.1f}%  Sharpe {w['oss']:.2f}  excess {w['oos_exc']*100:+.1f}%/yr")
    verdict = ("HOLDS — positive OOS excess & Sharpe" if w["oos_exc"] > 0 and w["oss"] > 0
               else "FAILS out of sample")
    print(f"  VERDICT: {verdict}")
    pos = sum(1 for k in rows if rows[k]["oos_exc"] > 0)
    print(f"\n  {pos}/{len(rows)} blends kept a POSITIVE OOS excess over universe "
          f"(robustness of the family, not just the winner).")


if __name__ == "__main__":
    main()
