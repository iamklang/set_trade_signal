#!/usr/bin/env python3
"""
bt_composite.py — walk-forward cross-sectional quintile backtest of composite.py on SET100.

Each month-end: rank every name with enough history by the composite factor blend
(momentum 12-1 + trend-above-SMA200 + low-vol), split into quintiles (Q1=top 20%),
hold equal-weight for one month, record forward returns. This is inherently walk-forward
/ point-in-time: every factor uses ONLY trailing data as of the rebalance date, and the
forward return is the NEXT month — no look-ahead.

Validation we care about:
  • MONOTONICITY  Q1 > Q2 > Q3 > Q4 > Q5 in mean forward return (the factor-quality tell).
  • Q1 vs universe (equal-weight all) — does trading the leaders beat buy-everything?
  • Q1-minus-Q5 long/short spread and its Sharpe.
  • Q1 long-only NET of turnover cost (retail SET ~0.30% one-way).
Metrics per sleeve: CAGR, Sharpe (from monthly), maxDD, profit factor, hit rate.

Yahoo data (long history; set_data only serves ~1yr, too short for 12-1 + walk-forward).
Usage: python bt_composite.py [--years 12] [--universe set100.bk.txt] [--cost 0.003]
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
import yfinance as yf

HERE = "/Users/klang/Git/trading_dr"
sys.path.insert(0, HERE)
import composite  # noqa: E402


def load_universe(path):
    with open(path) as f:
        return [t.split("#")[0].strip() for t in f if t.split("#")[0].strip()]


def fetch(tickers, years):
    """Yahoo daily closes -> {ticker: df} plus a combined month-end close matrix."""
    frames, closes = {}, {}
    for i, t in enumerate(tickers):
        try:
            df = yf.download(t, period=f"{years}y", interval="1d",
                             progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df is None or len(df) < composite.MIN_BARS:
                continue
            frames[t] = df
            closes[t] = df["Close"]
        except Exception as e:
            print(f"  skip {t}: {str(e)[:50]}")
        if (i + 1) % 20 == 0:
            print(f"  fetched {i + 1}/{len(tickers)} ...")
    px = pd.DataFrame(closes).sort_index()
    return frames, px


def metrics(r):
    """r: monthly return Series. Returns dict of headline stats."""
    r = r.dropna()
    if len(r) < 6:
        return {"n": len(r), "CAGR": np.nan, "Sharpe": np.nan,
                "maxDD": np.nan, "PF": np.nan, "hit": np.nan}
    eq = (1 + r).cumprod()
    yrs = len(r) / 12
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    sharpe = r.mean() / r.std() * np.sqrt(12) if r.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    pf = gains / losses if losses > 0 else np.inf
    return {"n": len(r), "CAGR": cagr, "Sharpe": sharpe,
            "maxDD": dd, "PF": pf, "hit": (r > 0).mean()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=12)
    ap.add_argument("--universe", default=os.path.join(HERE, "set100.bk.txt"))
    ap.add_argument("--cost", type=float, default=0.003, help="one-way cost frac (0.003=30bps)")
    ap.add_argument("--weights", default="1,1,1", help="mom,trend,lowvol weights")
    a = ap.parse_args()

    wl = [float(x) for x in a.weights.split(",")]
    weights = {"mom": wl[0], "trend": wl[1], "lowvol": wl[2]}

    tickers = load_universe(a.universe)
    print(f"SET100 composite walk-forward | {len(tickers)} names | {a.years}y | "
          f"weights mom/trend/lowvol={a.weights} | cost {a.cost*100:.2f}%/side\n")
    frames, px = fetch(tickers, a.years)
    print(f"\n  usable: {len(frames)} names, {px.index.min().date()}..{px.index.max().date()}\n")

    # month-end rebalance dates
    me = px.resample("ME").last()
    dates = me.index
    q_rets = {q: [] for q in range(1, 6)}      # quintile -> list of (date, mean_fwd_ret)
    uni_rets, q1_names_prev, turnover = [], set(), []

    for i in range(len(dates) - 1):
        d0, d1 = dates[i], dates[i + 1]
        R = composite.cross_section_scores(frames, asof=d0, weights=weights)
        if R.empty or len(R) < 20:
            continue
        # forward return over [d0, d1] per name from the month-end close matrix
        p0, p1 = me.loc[d0], me.loc[d1]
        fwd = (p1 / p0 - 1.0)
        R = R.join(fwd.rename("fwd"))
        R = R[R["fwd"].notna()]
        if len(R) < 20:
            continue
        for q in range(1, 6):
            sub = R[R["quintile"] == q]["fwd"]
            if len(sub):
                q_rets[q].append((d1, sub.mean()))
        uni_rets.append((d1, R["fwd"].mean()))
        q1 = set(R[R["quintile"] == 1].index)
        if q1_names_prev:
            turnover.append(1 - len(q1 & q1_names_prev) / max(len(q1_names_prev), 1))
        q1_names_prev = q1

    def series(pairs):
        return pd.Series({d: v for d, v in pairs}).sort_index()

    qser = {q: series(q_rets[q]) for q in range(1, 6)}
    uni = series(uni_rets)
    avg_turn = float(np.mean(turnover)) if turnover else 0.0
    q1_net = qser[1] - avg_turn * (2 * a.cost)          # round-trip cost * turnover
    ls = (qser[1] - qser[5]).dropna()                    # long-short Q1-Q5

    print("=" * 74)
    print(f"{'sleeve':<16}{'n':>4}{'CAGR':>9}{'Sharpe':>8}{'maxDD':>9}{'PF':>7}{'hit':>7}")
    print("-" * 74)
    def row(name, r):
        m = metrics(r)
        def f(x, p=1, pct=True):
            if x is None or (isinstance(x, float) and np.isnan(x)):
                return "  n/a"
            return f"{x*100:>{6}.{p}f}%" if pct else f"{x:>6.2f}"
        print(f"{name:<16}{m['n']:>4}{f(m['CAGR']):>9}{f(m['Sharpe'],2,False):>8}"
              f"{f(m['maxDD']):>9}{f(m['PF'],2,False):>7}{f(m['hit'],0):>7}")
    for q in range(1, 6):
        row(f"Q{q}" + (" (top)" if q == 1 else " (bottom)" if q == 5 else ""), qser[q])
    row("Q1 net-cost", q1_net)
    row("Universe(EW)", uni)
    row("Q1-Q5 L/S", ls)
    print("=" * 74)

    means = {q: qser[q].mean() * 100 for q in range(1, 6)}
    mono = all(means[q] >= means[q + 1] for q in range(1, 5))
    inv = sum(means[q] < means[q + 1] for q in range(1, 5))
    print(f"\nMonthly mean by quintile (%): " +
          "  ".join(f"Q{q} {means[q]:+.2f}" for q in range(1, 6)))
    print(f"Monotonic Q1>..>Q5: {mono}  ({inv} inversion(s))")
    print(f"Avg Q1 turnover/month: {avg_turn*100:.0f}%   "
          f"Q1 excess over universe (CAGR): "
          f"{(metrics(qser[1])['CAGR']-metrics(uni)['CAGR'])*100:+.1f}%/yr")
    print(f"\nInterpretation: a monotone Q1>..>Q5 + Q1 beating the universe net of cost = "
          f"the composite ranks real forward-return; flat/inverted = no edge on the SET.")


if __name__ == "__main__":
    main()
