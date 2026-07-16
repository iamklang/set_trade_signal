#!/usr/bin/env python3
"""
scan_ready.py — morning "ready list" for SET DW Swing.

Run BEFORE market open to see which stocks are one bar away from triggering.
Uses yesterday's closed data to pre-qualify names so the trader knows what to
watch during the session, hours before the EOD scan runs.

Categories (from most to least actionable):
  DIP READY      uptrend + recently touched EMA + RSI/ADX OK → needs green bar + volume
  BRK READY      uptrend + close near 20-day high → needs breakout + volume
  ALMOST         uptrend but one filter short (RSI/ADX/proximity)

Usage:
    python scan_ready.py                       # Q1 leaders (default)
    python scan_ready.py --all-quintiles       # show all
    python scan_ready.py --no-line             # skip LINE push
"""
import argparse
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import setdw_signal as sig
import bullish_signals as bull
import set_data
import profiles
import line_notify

BREAKOUT_NEAR_PCT = 2.0


def load_universe(path):
    with open(path) as f:
        return [t.split("#")[0].strip() for t in f if t.split("#")[0].strip()]


def load_ranks(max_age_h=72):
    path = os.path.join(HERE, "composite_rank.csv")
    if not os.path.exists(path):
        return {}
    if (time.time() - os.path.getmtime(path)) / 3600 > max_age_h:
        return {}
    try:
        df = pd.read_csv(path)
        return {str(r["ticker"]): int(r["quintile"])
                for _, r in df.iterrows() if pd.notna(r.get("quintile"))}
    except Exception:
        return {}


def classify(df, t, cfg):
    """Classify a stock's readiness on the LAST bar. Returns dict or None."""
    if df is None or len(df) < sig.SMA_LEN + 30:
        return None
    d = bull.add_signals(df, cfg)
    row = d.iloc[-1]
    close = float(row["Close"])
    ema = float(row["ema"])
    rsi = float(row["rsi"])
    adx = float(row["adx"])
    rsi_min = cfg.get("rsi_min", sig.RSI_MIN)

    trend_up = (close > ema and bool(row["emaUp"])
                and ema > float(row["sma"]) and bool(row["smaUp"]))

    near_ema = bool(row["llLook"] <= ema * (1 + sig.PROX)) and bool(row["freshprior"])
    dist_pct = (close - ema) / ema * 100

    prior_high = float(d["High"].rolling(bull.BREAKOUT_LOOK).max().shift(1).iloc[-1])
    dist_high_pct = (prior_high - close) / close * 100 if prior_high > 0 else 99

    rsi_ok = rsi >= rsi_min
    adx_ok = adx >= sig.ADX_MIN

    stop = float(row["llStop"])
    risk = close - stop if close > stop else 0
    t1 = close + risk if risk > 0 else close

    out = {
        "ticker": t, "close": close, "ema": round(ema, 2),
        "dist_pct": round(dist_pct, 2), "rsi": round(rsi, 1), "adx": round(adx, 1),
        "trend_up": trend_up, "near_ema": near_ema,
        "rsi_ok": rsi_ok, "adx_ok": adx_ok,
        "prior_high": round(prior_high, 2), "dist_high_pct": round(dist_high_pct, 2),
        "stop": round(stop, 2), "t1": round(t1, 2),
        "category": "NOT_READY", "missing": [],
    }

    if not trend_up:
        out["missing"].append("uptrend")
        return out

    if near_ema and rsi_ok and adx_ok:
        out["category"] = "DIP_READY"
        out["missing"] = ["green bar + vol"]
        return out

    if dist_high_pct <= BREAKOUT_NEAR_PCT and rsi_ok and adx_ok:
        out["category"] = "BRK_READY"
        pct_away = f"{dist_high_pct:+.1f}%" if dist_high_pct > 0 else "at high"
        out["missing"] = [f"close > {prior_high:.2f} ({pct_away}) + vol"]
        return out

    missing = []
    if not near_ema and dist_high_pct > BREAKOUT_NEAR_PCT:
        missing.append(f"proximity (EMA dist {dist_pct:+.1f}%, high dist {dist_high_pct:+.1f}%)")
    if not rsi_ok:
        missing.append(f"RSI {rsi:.0f} < {rsi_min}")
    if not adx_ok:
        missing.append(f"ADX {adx:.0f} < {sig.ADX_MIN}")
    if missing:
        out["category"] = "ALMOST"
        out["missing"] = missing
    else:
        out["category"] = "BRK_READY" if dist_high_pct <= BREAKOUT_NEAR_PCT else "DIP_READY"
        out["missing"] = ["green bar + vol"]

    return out


def build_report(ready, scan_date="", n_names=0, all_quintiles=False, in_trend=0):
    """Single source of truth for the morning ready-list brief — the SAME text is printed to
    the console AND pushed to LINE (no divergence). This is ONLY the morning-ready result:
    the DIP/BRK/ALMOST groups (close/RSI/ADX/stop/T1 + the trigger condition), a ready/almost
    tally, and the legend. Position management (holdings, sells, capital) is out of scope here
    — that belongs to the EOD alert (alert.py) and the eod-monitor."""
    lines = [f"SET DW Ready List | as of {scan_date} | {n_names} names"
             + ("" if all_quintiles else " | Q1-Q2 only"), ""]

    cats = {"DIP_READY": "DIP READY", "BRK_READY": "BRK READY", "ALMOST": "ALMOST"}
    any_ready = False
    for cat_key, cat_label in cats.items():
        group = [r for r in ready if r["category"] == cat_key]
        if not group:
            continue
        any_ready = True
        lines.append(f"  === {cat_label} ({len(group)}) ===")
        for r in group:
            q = f"Q{r['quintile']}" if r.get("quintile") else " - "
            nm = r["ticker"].replace(".BK", "")
            star = "★" if r.get("quintile") == 1 else " "
            lines.append(f"  {star}{nm:11s}{q:>3s}  close {r['close']:>8.2f}  RSI {r['rsi']:>4.0f}"
                         f"  ADX {r['adx']:>4.0f}  stop {r['stop']:>8.2f}  T1 {r['t1']:>8.2f}"
                         f"  | {', '.join(r['missing'])}")
        lines.append("")

    if not any_ready:
        lines.append("  ไม่มีตัวใกล้ trigger วันนี้\n")

    total_ready = len([r for r in ready if r["category"] in ("DIP_READY", "BRK_READY")])
    n_almost = len([r for r in ready if r["category"] == "ALMOST"])
    lines.append(f"  {total_ready} ready + {n_almost} almost (out of {in_trend} in-trend names)")
    lines.append("  ★=Q1 leader · DIP=ย่อชน EMA เด้ง · BRK=ทะลุ high 20 วัน")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="SET morning ready-list scanner")
    ap.add_argument("--universe", default=os.path.join(HERE, "set100.bk.txt"))
    ap.add_argument("--all-quintiles", action="store_true",
                    help="show all quintiles (default: Q1-Q2 only)")
    ap.add_argument("--source", default="yahoo", choices=["set", "yahoo"])
    ap.add_argument("--no-line", action="store_true")
    ap.add_argument("--no-profile", action="store_true")
    a = ap.parse_args()

    tickers = load_universe(a.universe)
    print(f"fetching {len(tickers)} names ...")
    frames = set_data.fetch_yahoo_all(tickers)
    ranks = load_ranks()
    if not ranks:
        print("  ⚠ composite_rank.csv missing/stale — quintile filter off")

    base_cfg = {"rsi_min": sig.RSI_MIN, "adx_min": sig.ADX_MIN,
                "maxext": 0.0, "need_vol_conf": True}

    results = []
    scan_date = None
    for t in tickers:
        df = frames.get(t)
        cfg = base_cfg if a.no_profile else profiles.cfg_for(t, base_cfg)
        r = classify(df, t, cfg)
        if r is None:
            continue
        if scan_date is None and df is not None and len(df):
            scan_date = str(df.index[-1].date())
        r["quintile"] = ranks.get(t)
        results.append(r)

    if not a.all_quintiles and ranks:
        results = [r for r in results if r.get("quintile") in (1, 2)]

    ready = [r for r in results if r["category"] in ("DIP_READY", "BRK_READY", "ALMOST")]
    ready.sort(key=lambda r: ({"DIP_READY": 0, "BRK_READY": 1, "ALMOST": 2}[r["category"]],
                               r.get("quintile") or 99))

    # One report -> console AND LINE (identical text, single formatter). Morning-ready result
    # only — the ready-list; position management lives in alert.py / eod-monitor, not here.
    report = build_report(ready, scan_date or "", n_names=len(tickers),
                          all_quintiles=a.all_quintiles, in_trend=len(results))
    print("\n" + report + "\n")

    if not a.no_line:
        if line_notify.send_line_push(report):
            print("  LINE ready-list sent.")
        else:
            print("  LINE skipped (no credentials or send failed).")


if __name__ == "__main__":
    main()
