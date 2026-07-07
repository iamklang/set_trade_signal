#!/usr/bin/env python3
"""
bt_triggers.py — how do the bull-scan "★ Q1 leader + trigger" signals relate to the strict
BUY(dip) that feeds the managed watchlist? Two questions:

  1. OVERLAP — how often does each trigger (dip / breakout / reclaim) fire, how much do they
     co-occur, and what share are composite-Q1 leaders? (dip vs breakout should be ~disjoint.)
  2. FORWARD EDGE — enter on each trigger (and on "any actionable = dip|breakout|reclaim"),
     run the SAME V5 let-winners-run exit, split by Q1-leader vs not. Which trigger+leader
     combo actually pays — i.e. should the watchlist widen beyond dip-only?

SET100/Yahoo. NOT advice. Reuses setdw_signal + bullish_signals + composite.
"""
import argparse
import bisect
import sys

import numpy as np
import pandas as pd

HERE = "/Users/klang/Git/trading_dr"
sys.path.insert(0, HERE)
import setdw_signal as sig          # noqa: E402
import bullish_signals as bull      # noqa: E402
import composite                    # noqa: E402
import set_data                     # noqa: E402

COST = 0.003
COOLDOWN = 5
TRIGGERS = ["dip", "breakout", "reclaim"]      # actionable (exclude broad 'trend'/'golden')


def load_universe(path):
    with open(path) as f:
        return [t.split("#")[0].strip() for t in f if t.split("#")[0].strip()]


def prep(df):
    cfg = {"rsi_min": sig.RSI_MIN, "adx_min": sig.ADX_MIN, "need_vol_conf": True}
    return bull.add_signals(df, cfg)          # adds dip/breakout/reclaim/trend + ema + llStop


def monthly_quint(frames, dates):
    me = pd.Series(index=dates, data=0).resample("ME").last().index
    out = {}
    for d in me:
        R = composite.cross_section_scores(frames, asof=d,
                                           weights={"mom": 1, "trend": 1, "lowvol": 0})
        out[d] = {} if R.empty else {t: int(R.loc[t, "quintile"]) for t in R.index}
    return sorted(out), out


def sim_v5(d, i):
    """V5 let-run trade opened at bar i's close. Return net %return (or None)."""
    o = d["Open"].values; h = d["High"].values; l = d["Low"].values
    c = d["Close"].values; ema = d["ema"].values; ll = d["llStop"].values
    entry, stop = c[i], ll[i]
    if not (entry > stop > 0):
        return None
    cur_stop, t1 = stop, entry + (entry - stop)
    t1_hit = False
    for j in range(i + 1, len(d)):
        if l[j] <= cur_stop:
            return (min(o[j], cur_stop) - entry) / entry - 2 * COST
        if not t1_hit and h[j] >= t1:
            t1_hit = True; cur_stop = entry
        if t1_hit and c[j] < ema[j]:
            return (c[j] - entry) / entry - 2 * COST
    return (c[-1] - entry) / entry - 2 * COST


def stats(rets):
    r = np.array(rets)
    if len(r) == 0:
        return None
    w, l = r[r > 0].sum(), -r[r < 0].sum()
    return dict(n=len(r), win=(r > 0).mean() * 100, avg=r.mean() * 100,
                pf=(w / l if l > 0 else np.inf), sm=r.sum() * 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--universe", default=f"{HERE}/set100.bk.txt")
    a = ap.parse_args()

    tickers = load_universe(a.universe)
    print(f"fetching {len(tickers)} names, {a.years}y ...")
    raw = set_data.fetch_yahoo_all(tickers, period=f"{a.years}y")
    frames = {t: prep(df) for t, df in raw.items()
              if df is not None and len(df) >= sig.SMA_LEN + 60}
    any_dates = sorted(set().union(*[set(d.index) for d in frames.values()]))
    print(f"usable {len(frames)} names; monthly composite ...")
    months, mq = monthly_quint({t: raw[t] for t in frames}, pd.DatetimeIndex(any_dates))

    def quint(t, ts):
        i = bisect.bisect_right(months, ts) - 1
        return mq[months[i]].get(t) if i >= 0 else None

    # ---- 1) OVERLAP -----------------------------------------------------------------------
    fires = {s: 0 for s in TRIGGERS}
    co = {(x, y): 0 for x in TRIGGERS for y in TRIGGERS}
    q1 = {s: 0 for s in TRIGGERS}
    for t, d in frames.items():
        for s in TRIGGERS:
            col = d[s].values
            fires[s] += int(col.sum())
        for s in TRIGGERS:
            idx = np.where(d[s].values)[0]
            for x in TRIGGERS:
                co[(s, x)] += int(d[x].values[idx].sum())
            # Q1 share
            for k in idx:
                if quint(t, d.index[k]) == 1:
                    q1[s] += 1

    print("\n=== 1) OVERLAP (how the triggers relate) ===")
    print(f"{'trigger':>9}{'fires':>8}{'%Q1':>6}   co-occurrence same-bar with →")
    print(f"{'':>23}" + "".join(f"{x:>10}" for x in TRIGGERS))
    for s in TRIGGERS:
        q1pct = 100 * q1[s] / fires[s] if fires[s] else 0
        cells = "".join(f"{100*co[(s,x)]/fires[s]:>9.0f}%" if fires[s] else f"{'-':>10}"
                        for x in TRIGGERS)
        print(f"{s:>9}{fires[s]:>8}{q1pct:>5.0f}%   {cells}")
    print("  read: row=given this trigger fired, %Q1 = share that were Q1 leaders; the cells = "
          "% of those bars that ALSO had the column trigger (100 on the diagonal).")

    # ---- 2) FORWARD EDGE (V5 exit), by trigger x leader -----------------------------------
    print("\n=== 2) FORWARD EDGE — enter on trigger, V5 let-run exit, split by Q1 ===")
    print(f"{'entry':>16}{'leader':>8}{'n':>7}{'win%':>7}{'avg%':>7}{'PF':>6}{'sum%':>8}")
    print("-" * 59)

    def run_entry(is_fire, leaders_only):
        rets = []
        for t, d in frames.items():
            fire = is_fire(d)
            i, n, last = 0, len(d), -10_000
            while i < n:
                if fire[i] and (i - last) >= COOLDOWN:
                    if leaders_only and quint(t, d.index[i]) != 1:
                        i += 1; continue
                    r = sim_v5(d, i)
                    if r is not None:
                        rets.append(r)
                        # advance past the trade (approx: to next signal) — use cooldown gap
                        last = i
                i += 1
        return rets

    entries = {
        "dip":        lambda d: d["dip"].values,
        "breakout":   lambda d: d["breakout"].values,
        "reclaim":    lambda d: d["reclaim"].values,
        "any-trigger": lambda d: (d["dip"] | d["breakout"] | d["reclaim"]).values,
    }
    for name, fn in entries.items():
        for lab, lo in (("all", False), ("Q1", True)):
            s = stats(run_entry(fn, lo))
            if s:
                print(f"{name:>16}{lab:>8}{s['n']:>7}{s['win']:>7.1f}{s['avg']:>7.2f}"
                      f"{s['pf']:>6.2f}{s['sm']:>8.0f}")
        print()


if __name__ == "__main__":
    main()
