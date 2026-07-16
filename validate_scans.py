#!/usr/bin/env python3
"""
validate_scans.py — re-run the BUY(dip) signal for every row in each
dip_scan_*.csv and append a validated/validated_date column.

For each ticker+scan_date, fetches fresh data and checks whether the signal
still fires on that bar. Writes the result back into the CSV.

Uses SET data by default; falls back to Yahoo automatically when SET data
is too short for older scan dates.

Usage:
    ~/.venvs/trading-dr/bin/python validate_scans.py
    ~/.venvs/trading-dr/bin/python validate_scans.py --file dip_scan_2026-06-26.csv
    ~/.venvs/trading-dr/bin/python validate_scans.py --source yahoo
"""
import argparse
import glob
import os
import re
import sys
from datetime import datetime

import pandas as pd
import yfinance as yf

import setdw_signal as sig
import set_data
import profiles
import market

HERE = os.path.dirname(os.path.abspath(__file__))

_TS_RE = re.compile(r"dip_scan_(\d{4}-\d{2}-\d{2})")
MIN_BARS = sig.SMA_LEN + 5


def parse_scan_date(filename):
    m = _TS_RE.search(filename)
    return m.group(1) if m else None


def _fetch_yahoo(ticker):
    df = yf.download(ticker, period="5y", interval="1d",
                     progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df if len(df) > 0 else None


def validate_one(ticker, scan_date, df_price):
    """Re-run signal on the scan_date bar. Returns (bool, reason, source_used)."""
    if df_price is None or len(df_price) < MIN_BARS:
        return None, "insufficient data", None
    asof = pd.Timestamp(scan_date)
    df = df_price[df_price.index <= asof]
    if len(df) < MIN_BARS:
        return None, "no data before date", None
    bar_date = df.index[-1].date()
    if abs((bar_date - asof.date()).days) > 5:
        return None, f"nearest bar {bar_date} too far from {scan_date}", None
    df = sig.add_indicators(df)
    cfg = profiles.cfg_for(ticker, {
        "rsi_min": sig.RSI_MIN, "adx_min": sig.ADX_MIN,
        "maxext": 0.0, "need_vol_conf": True,
    })
    fired = bool(sig.buy_signal(df, cfg).iloc[-1])
    if fired:
        return True, "confirmed", None
    row = df.iloc[-1]
    reasons = []
    c = float(row["Close"])
    if not (c > row["ema"] and row["emaUp"] and row["ema"] > row["sma"] and row["smaUp"]):
        reasons.append("not-uptrend")
    if not bool(row["green"]):
        reasons.append("not-green")
    if not (row["llLook"] <= row["ema"] * (1 + sig.PROX) and row["freshprior"]):
        reasons.append("no-fresh-dip")
    if row["rsi"] < cfg["rsi_min"]:
        reasons.append(f"rsi {row['rsi']:.0f}<{cfg['rsi_min']}")
    if row["adx"] < sig.ADX_MIN:
        reasons.append(f"adx {row['adx']:.0f}<{sig.ADX_MIN}")
    if row["Volume"] <= row["volSma"]:
        reasons.append("low-vol")
    return False, ", ".join(reasons) or "setup incomplete", None


def main():
    ap = argparse.ArgumentParser(description="Validate dip_scan CSV results")
    ap.add_argument("--market", default=None, help="market profile: set (default) | us")
    ap.add_argument("--file", default=None, help="validate a specific CSV (default: all)")
    ap.add_argument("--source", default="set", choices=["set", "yahoo"])
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--cache-hours", type=float, default=4,
                    help="reuse cached data if younger than N hours (default 4)")
    a = ap.parse_args()
    market.set_market(a.market)

    if a.file:
        files = [a.file]
    else:
        files = sorted(glob.glob(os.path.join(market.scans_dir(), "dip_scan_*.csv")))

    if not files:
        print("no dip_scan_*.csv files found.")
        return

    need_tickers = set()          # only tickers with an UNDECIDED row need fresh data
    file_data = []
    for fpath in files:
        scan_date = parse_scan_date(os.path.basename(fpath))
        if not scan_date:
            continue
        df = pd.read_csv(fpath)
        if df.empty or "ticker" not in df.columns:
            continue
        if "validated" not in df.columns:
            need_tickers.update(df["ticker"].tolist())
        else:
            decided = df["validated"].astype(str).isin(["True", "False"])
            need_tickers.update(df.loc[~decided, "ticker"].tolist())
        file_data.append((fpath, scan_date, df))

    if not file_data:
        print("no valid CSV files to validate.")
        return

    tickers = sorted(need_tickers)

    # Fetch primary source — ONLY for tickers with undecided rows (decided rows are frozen,
    # so a fully-validated backlog fetches nothing and the run is near-instant).
    if not tickers:
        print("  all scan rows already validated — no fetch needed.")
        frames = {}
    else:
        print(f"  fetching data ({a.source}) for {len(tickers)} tickers (undecided rows)...")
        if a.source == "set":
            frames = set_data.fetch_all(tickers, concurrency=a.concurrency,
                                        cache_hours=a.cache_hours)
        else:
            frames = {}
            for t in tickers:
                frames[t] = _fetch_yahoo(t)

    # Find earliest scan date to check if we need Yahoo fallback
    earliest = min(sd for _, sd, _ in file_data)
    yahoo_frames = {}

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_ok, total_fail, total_err = 0, 0, 0

    for fpath, scan_date, df in file_data:
        fname = os.path.basename(fpath)
        has_prev = "validated" in df.columns
        results = []
        for _, row in df.iterrows():
            # Skip rows already DECIDED (True or False) on their fixed, historical scan bar —
            # a confirmed/failed signal on a past bar never changes, so re-fetching and
            # re-checking it every day is wasted work that grows with every scan file. Only
            # undecided rows (None / errored / a brand-new scan with no 'validated' column)
            # are (re)validated below.
            prev = str(row.get("validated")) if has_prev else ""
            if prev in ("True", "False"):
                results.append({
                    "validated": prev == "True",
                    "validate_reason": row.get("validate_reason", ""),
                    "validated_at": row.get("validated_at", ""),
                })
                if prev == "True":
                    total_ok += 1
                else:
                    total_fail += 1
                continue

            ticker = row["ticker"]
            df_price = frames.get(ticker)

            # Try primary source first
            ok, reason, _ = validate_one(ticker, scan_date, df_price)

            # Fallback to Yahoo if SET data too short
            if ok is None and a.source == "set" and "data" in reason:
                if ticker not in yahoo_frames:
                    print(f"    {ticker}: SET data too short, fetching Yahoo...")
                    yahoo_frames[ticker] = _fetch_yahoo(ticker)
                ok, reason, _ = validate_one(ticker, scan_date, yahoo_frames[ticker])
                if ok is not None:
                    reason += " (yahoo)"

            results.append({"validated": ok, "validate_reason": reason, "validated_at": None})
            if ok is True:
                total_ok += 1
            elif ok is False:
                total_fail += 1
            else:
                total_err += 1

        vdf = pd.DataFrame(results)
        # strip old columns before writing new ones
        for col in ["validated", "validate_reason", "validated_at"]:
            if col in df.columns:
                df = df.drop(columns=[col])
        df["validated"] = vdf["validated"].values
        df["validate_reason"] = vdf["validate_reason"].values
        df["validated_at"] = [r["validated_at"] or now_str for r in results]
        df.to_csv(fpath, index=False)

        ok_count = sum(1 for r in results if r["validated"] is True)
        fail_count = sum(1 for r in results if r["validated"] is False)
        err_count = sum(1 for r in results if r["validated"] is None)
        status = "ALL OK" if fail_count == 0 and err_count == 0 else f"{fail_count} FAILED"
        print(f"  {fname}: {len(results)} rows — {ok_count} confirmed, "
              f"{fail_count} failed, {err_count} error — {status}")

    print(f"\n  total: {total_ok} confirmed, {total_fail} failed, {total_err} error")
    print(f"  validated at {now_str}\n")


if __name__ == "__main__":
    main()
