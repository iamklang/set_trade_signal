#!/usr/bin/env python3
"""
collect_nvdr.py — append today's per-stock NVDR (foreign-proxy) snapshot to nvdr_history.csv.

The SET only serves the LATEST session's NVDR (no history endpoint — verified 2026-07-06), so the
only way to get a backtestable NVDR-flow series is to COLLECT it forward. Run this once per session
(fold into daily_scan) and after a few months there is enough history to test NVDR net flow as a 3rd
weak signal in the composite (the Medallion "many weak independent signals" idea). Until then it is a
LIVE context signal only — do NOT mechanise it without a validated backtest.

Row schema: date, symbol, net, net_pct   (dedup by date+symbol; idempotent per day).
Usage: ~/.venvs/trading-dr/bin/python collect_nvdr.py
"""
import os
import sys

import pandas as pd

import set_data

HERE = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(HERE, "nvdr_history.csv")


def main():
    try:
        date, snap = set_data.fetch_nvdr()
    except Exception as e:
        print(f"[ERROR] NVDR fetch failed: {e}")
        return 2
    if not date or not snap:
        print("[warn] empty NVDR snapshot — nothing to append")
        return 1
    rows = [{"date": date, "symbol": s, "net": v["net"], "net_pct": v["net_pct"]}
            for s, v in snap.items()]
    new = pd.DataFrame(rows)

    if os.path.exists(HIST):
        old = pd.read_csv(HIST)
        if str(date) in old["date"].astype(str).values:
            print(f"  NVDR {date} already collected ({len(old)} rows total) — skip")
            return 0
        out = pd.concat([old, new], ignore_index=True)
    else:
        out = new
    out.to_csv(HIST, index=False)
    dates = out["date"].nunique()
    print(f"  appended NVDR {date}: {len(new)} names -> {HIST} "
          f"({len(out)} rows, {dates} session(s) collected)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
