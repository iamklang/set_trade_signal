#!/usr/bin/env python3
"""
bt_quality.py — does adding the SET ROE quality factor help the composite?

Honest small-sample test: SET's financial-data endpoint only serves ~4 annual ROE rows
(2022-2025), so a quality backtest can only cover ~2023-04..2026 (need a reported prior
fiscal year, lagged for publication). We compare, on the SAME quality-available months so
it is apples-to-apples, the price-only mom+trend blend vs mom+trend+quality at a few weights.

Point-in-time ROE: for rebalance month m in year Y, use fiscal year Y-1 if m>=April (annual
results are public by ~Q1), else Y-2 — never a year whose results weren't out yet.

Price frames reused from bt_composite's cache; ROE history fetched once via
set_data.fetch_fundamentals(history=True) and cached. Usage: python bt_quality.py
"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = "/Users/klang/Git/trading_dr"
sys.path.insert(0, HERE)
import composite  # noqa: E402
import set_data   # noqa: E402

SCR = "/private/tmp/claude-501/-Users-klang-Git-trading-dr/e1883bdb-3ed2-41b2-bd5f-cccf9e269bb2/scratchpad"
PX_CACHE = f"{SCR}/_px_cache.pkl"
ROE_CACHE = f"{SCR}/_roe_hist.pkl"

VARIANTS = {
    "mom+trend (1,1,0,0)":   {"mom": 1, "trend": 1, "lowvol": 0, "quality": 0},
    "+qual×0.5 (1,1,0,.5)":  {"mom": 1, "trend": 1, "lowvol": 0, "quality": 0.5},
    "+qual×1  (1,1,0,1)":    {"mom": 1, "trend": 1, "lowvol": 0, "quality": 1},
    "qual only (0,0,0,1)":   {"mom": 0, "trend": 0, "lowvol": 0, "quality": 1},
}


def usable_year(d0):
    return d0.year - 1 if d0.month >= 4 else d0.year - 2


def stats(r):
    r = r.dropna()
    if len(r) < 6:
        return np.nan, np.nan
    cagr = (1 + r).prod() ** (12 / len(r)) - 1
    sharpe = r.mean() / r.std() * np.sqrt(12) if r.std() > 0 else np.nan
    return cagr, sharpe


def main():
    frames = pickle.load(open(PX_CACHE, "rb"))["frames"]
    tickers = list(frames)
    if os.path.exists(ROE_CACHE):
        roe_hist = pickle.load(open(ROE_CACHE, "rb"))
        print(f"  (cached ROE history: {len(roe_hist)} names)")
    else:
        print(f"  fetching ROE history for {len(tickers)} names ...")
        roe_hist = set_data.fetch_fundamentals(tickers, concurrency=6, history=True)
        pickle.dump(roe_hist, open(ROE_CACHE, "wb"))
    yrs = sorted({y for m in roe_hist.values() if m for y in m})
    print(f"  ROE fiscal years available: {yrs}\n")

    px = pd.DataFrame({t: frames[t]["Close"] for t in frames}).sort_index()
    me = px.resample("ME").last()
    dates = me.index

    series = {name: {"q1": {}, "uni": {}} for name in VARIANTS}
    used_months = 0
    for i in range(len(dates) - 1):
        d0, d1 = dates[i], dates[i + 1]
        uy = usable_year(d0)
        qmap = {t: (roe_hist.get(t) or {}).get(uy) for t in tickers}
        if sum(1 for v in qmap.values() if v is not None) < 20:
            continue                                    # not enough ROE that month -> skip
        used_months += 1
        fwd = me.loc[d1] / me.loc[d0] - 1.0
        for name, w in VARIANTS.items():
            R = composite.cross_section_scores(frames, asof=d0, weights=w, quality=qmap)
            if R.empty:
                continue
            R = R.join(fwd.rename("fwd"))
            R = R[R["fwd"].notna()]
            q1 = R[R["quintile"] == 1]["fwd"]
            if len(q1):
                series[name]["q1"][d1] = q1.mean()
            series[name]["uni"][d1] = R["fwd"].mean()

    print(f"  quality-available rebalance months: {used_months} "
          f"({dates[0].date()}..{dates[-1].date()} window, restricted)\n")
    print("=" * 68)
    print(f"{'blend':<22}{'Q1 CAGR':>10}{'Sharpe':>9}{'exc/yr':>9}{'months':>8}")
    print("-" * 68)
    base_uni = None
    for name in VARIANTS:
        q1 = pd.Series(series[name]["q1"]).sort_index()
        uni = pd.Series(series[name]["uni"]).sort_index()
        c, s = stats(q1)
        exc = c - stats(uni)[0]
        print(f"{name:<22}{c*100:>9.1f}%{s:>9.2f}{exc*100:>+8.1f}%{len(q1):>8}")
        base_uni = uni
    print(f"{'Universe(EW)':<22}{stats(base_uni)[0]*100:>9.1f}%{stats(base_uni)[1]:>9.2f}"
          f"{'—':>9}{len(base_uni):>8}")
    print("=" * 68)
    print("\nRead: if +quality raises Q1 CAGR/Sharpe/excess over mom+trend on the SAME months,")
    print("the SET ROE factor adds value; if flat/worse, keep it small or off. Small sample —")
    print("~3-4yr of annual ROE only; directional, not conclusive.")


if __name__ == "__main__":
    main()
