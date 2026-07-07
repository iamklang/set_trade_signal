#!/usr/bin/env python3
"""
scan_bull.py — broad EOD bullish-signal scanner for a SET universe.

Companion to scan_dip.py: instead of only the narrow BUY(dip), it surfaces every name
firing ANY of the bullish_signals set (trend / breakout / reclaim / golden / dip) on the
last closed bar, tags each with the composite mom+trend quintile (Q1 = trend leader), and
prints an entry plan (structural stop / R-targets / size). Sort defaults to composite so the
strongest-trend names float to the top.

    python scan_bull.py                                  # SET100, all bullish signals
    python scan_bull.py --signals breakout,reclaim       # only actionable triggers
    python scan_bull.py --leaders-only --min-adx 20      # Q1 leaders with real trend strength
    python scan_bull.py --source yahoo --asof 2026-06-30

CANDIDATE list only — macro/sector/earnings judgment + DW selection still applied by hand.
Data is EOD; run after the SET close (bar posts overnight — see set_data notes).
"""
import argparse
import os
import sys
from datetime import date, datetime

import pandas as pd
import yfinance as yf

import setdw_signal as sig
import bullish_signals as bull
import set_data
import composite as comp_mod
import profiles
import line_notify

try:
    import exchange_calendars as xcals
    _CAL = xcals.get_calendar("XBKK")
except Exception:
    _CAL = None

HERE = os.path.dirname(os.path.abspath(__file__))


def load_universe(path):
    try:
        with open(path) as f:
            out = [t.split("#")[0].strip() for t in f if t.split("#")[0].strip()]
    except FileNotFoundError:
        sys.exit(f"universe file not found: {path}")
    if not out:
        sys.exit(f"universe file empty: {path}")
    return out


def fetch_yahoo(t, period="2y"):
    df = yf.download(t, period=period, interval="1d", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def parse_args():
    p = argparse.ArgumentParser(description="SET broad bullish-signal scanner")
    p.add_argument("--universe", default=os.path.join(HERE, "set100.bk.txt"))
    p.add_argument("--equity", type=float, default=1_000_000)
    p.add_argument("--risk", type=float, default=1.0)
    p.add_argument("--signals", default="all",
                   help="comma list to require (any-of) from dip,breakout,reclaim,golden,trend; "
                        "'all' = any bullish signal (default)")
    p.add_argument("--min-adx", type=float, default=0.0, help="drop names with ADX below this")
    p.add_argument("--source", default="yahoo", choices=["set", "yahoo"])
    p.add_argument("--concurrency", type=int, default=6)
    p.add_argument("--cache-hours", type=float, default=0)
    p.add_argument("--asof", default=None, help="evaluate as of YYYY-MM-DD (default: latest bar)")
    p.add_argument("--no-profile", action="store_true", help="ignore per-stock profiles.py")
    p.add_argument("--comp-weights", default="1,1,0", help="composite mom,trend,lowvol[,quality]")
    p.add_argument("--leaders-only", action="store_true", help="keep only composite Q1 leaders")
    p.add_argument("--sort", default="comp", choices=["comp", "adx", "dist"], help="sort key (desc)")
    p.add_argument("--csv", default=None, help="CSV output path (default: bull_scan_<date>.csv)")
    p.add_argument("--no-line", action="store_true", help="disable the LINE push (shortlist)")
    return p.parse_args()


def main():
    a = parse_args()
    want = None if a.signals.strip().lower() == "all" else \
        [s.strip() for s in a.signals.split(",") if s.strip()]
    if want:
        bad = [s for s in want if s not in bull.SIGNAL_COLS]
        if bad:
            sys.exit(f"unknown signal(s): {bad}; choose from {bull.SIGNAL_COLS}")

    tickers = load_universe(a.universe)
    asof = pd.Timestamp(a.asof) if a.asof else None

    # fetch
    if a.source == "set":
        frames = set_data.fetch_all(tickers, concurrency=a.concurrency, cache_hours=a.cache_hours)
    else:
        frames = set_data.fetch_yahoo_all(tickers)      # one batch call, no WAF

    # evaluate signals on the last (<= asof) bar
    hits, missing, asof_date, trend_total = [], [], None, 0
    for t in tickers:
        df = frames.get(t)
        if df is None or len(df) < sig.SMA_LEN + 30:
            missing.append(t); continue
        if asof is not None:
            df = df[df.index <= asof]
            if len(df) < sig.SMA_LEN + 30:
                missing.append(t); continue
        cfg = None if a.no_profile else profiles.cfg_for(t, {
            "rsi_min": sig.RSI_MIN, "adx_min": sig.ADX_MIN, "maxext": 0.0, "need_vol_conf": True})
        d = bull.add_signals(df, cfg)
        row = d.iloc[-1]
        asof_date = d.index[-1].date()
        if bool(row["trend"]):
            trend_total += 1          # true breadth (before any --signals/leaders filter)
        fired = bull.fired_on_row(row)
        if want:
            fired = [s for s in fired if s in want]
        if not fired:
            continue
        if float(row["adx"]) < a.min_adx:
            continue
        plan = sig.trade_plan(row, a.equity, a.risk)
        plan["signals"] = fired
        hits.append((t, plan))

    asof_str = (asof_date or date.today()).isoformat()

    # composite quintile tag — prefer the ranking file (scan_dip --composite / morning job);
    # 12-1 momentum needs ~12mo history, which SET data (~1yr) can't warm, so recomputing off
    # SET frames yields nothing. Fall back to an inline Yahoo-based ranking only if no file.
    ranks, comps = {}, {}
    rpath = os.path.join(HERE, "composite_rank.csv")
    if os.path.exists(rpath):
        try:
            rdf = pd.read_csv(rpath)
            for r in rdf.itertuples():
                if pd.notna(r.quintile):
                    ranks[str(r.ticker)] = int(r.quintile)
                if pd.notna(r.composite):
                    comps[str(r.ticker)] = float(r.composite)
        except Exception:
            pass
    if not ranks:                       # fallback: compute inline (Yahoo history for momentum)
        cw = [float(x) for x in a.comp_weights.split(",")]
        while len(cw) < 3:
            cw.append(0.0)
        weights = {"mom": cw[0], "trend": cw[1], "lowvol": cw[2]}
        cframes = frames if a.source == "yahoo" else {t: fetch_yahoo(t) for t in tickers}
        comp = comp_mod.cross_section_scores(cframes, asof=asof, weights=weights)
        if not comp.empty:
            ranks = {t: int(comp.loc[t, "quintile"]) for t in comp.index}
            comps = {t: float(comp.loc[t, "composite"]) for t in comp.index}
        else:
            print("  ⚠ no composite_rank.csv and inline ranking empty — quintiles unavailable")
    # Same size tilt as scan_dip/alert (quintile × market-regime brake) so a name that shows up
    # in BOTH the bull shortlist and the dip alert never displays two different sizes.
    regime_factor, regime_age = sig.load_market_regime(os.path.join(HERE, "market_regime.json"))
    if regime_age is None:
        print("  ⚠ market_regime.json missing — regime brake NOT applied to sizes below")
    elif regime_age > 48:
        print(f"  ⚠ market_regime.json stale ({regime_age:.0f}h) — regime brake NOT applied")
    elif regime_factor < 1.0:
        print(f"  ⚠ MARKET RISK-OFF → regime brake ON, size ×{regime_factor}")
    for t, p in hits:
        p["quintile"] = ranks.get(t)
        p["comp"] = comps.get(t)
        sig.apply_size_tilt(p, p["quintile"], regime_factor)
    if a.leaders_only and ranks:
        hits = [(t, p) for t, p in hits if p.get("quintile") == 1]

    # sort
    keymap = {"comp": lambda x: (x[1].get("comp") if x[1].get("comp") is not None else -9),
              "adx": lambda x: x[1]["adx"], "dist": lambda x: x[1]["distPct"]}
    hits.sort(key=keymap[a.sort], reverse=True)

    # report
    print(f"\nSET bullish scan | src {a.source} | as of {asof_str} | {a.universe} ({len(tickers)} names) "
          f"| signals={a.signals}" + (f" | min-adx {a.min_adx:g}" if a.min_adx else "")
          + (" | leaders-only" if a.leaders_only else "")
          + ("" if a.no_profile else f" | profiles on") + "\n")
    tally = {s: sum(1 for _, p in hits if s in p["signals"]) for s in bull.SIGNAL_COLS}
    if not hits:
        print("  no bullish signals.\n")
    else:
        hdr = (f"{'ticker':12s}{'Q':>2s}{'close':>9s}{'dist%':>7s}{'RSI':>5s}{'ADX':>5s}"
               f"{'stop':>9s}{'T1':>9s}{'T2':>9s}{'size':>8s}  signals")
        print(hdr); print("-" * len(hdr))
        for t, p in hits:
            q = str(p.get("quintile") or "-")
            star = "★" if p.get("quintile") == 1 else " "
            print(f"{star}{t.replace('.BK',''):11s}{q:>2s}{p['close']:>9.2f}{p['distPct']:>+7.1f}"
                  f"{p['rsi']:>5.0f}{p['adx']:>5.0f}{p['stop']:>9.2f}{p['t1']:>9.2f}{p['t2']:>9.2f}"
                  f"{p['size']:>8,d}  {','.join(p['signals'])}")
        print(f"\n  {len(hits)} name(s) | uptrend {trend_total}/{len(tickers)} | by signal: "
              + "  ".join(f"{s}={n}" for s, n in tally.items() if n))
        print(f"  ★ = composite Q1 leader (mom+trend)")

    if missing:
        print(f"\n  skipped {len(missing)} (no/short data)")

    # LINE push: shortlist = Q1 leaders with an ACTIONABLE trigger (dip/breakout/reclaim),
    # + signal legend + auto analysis (tight/low-risk vs extended vs overbought).
    TRIGGERS = ("dip", "breakout", "reclaim")
    shortlist = [{"ticker": t, "signals": p["signals"], "close": p["close"],
                  "distPct": p["distPct"], "rsi": p["rsi"], "adx": p["adx"],
                  "buy": p.get("buy", p["close"]), "stop": p["stop"], "t1": p["t1"],
                  "size": p["size"]}
                 for t, p in hits
                 if p.get("quintile") == 1 and any(s in TRIGGERS for s in p["signals"])]
    if shortlist:
        print(f"\n  ★ Q1 leader + trigger ({len(shortlist)}): "
              + ", ".join(h["ticker"].replace(".BK", "") for h in shortlist))
    # Always persist the formatted bull section so the 08:00 alert can fold it into ONE
    # combined LINE brief; only push it directly when NOT running inside that pipeline.
    msg = line_notify.format_bull_message(shortlist, len(tickers), trend_total,
                                          tally, scan_date=asof_str)
    try:
        with open(os.path.join(HERE, "bull_msg.txt"), "w") as f:
            f.write(msg)
    except OSError:
        pass
    if not a.no_line:
        if line_notify.send_line_push(msg):
            print("  LINE bull shortlist sent.")
        else:
            print("  LINE skipped (no credentials or send failed).")
    else:
        print("  bull section saved to bull_msg.txt (LINE suppressed — folded into alert)")

    # CSV
    csv_path = a.csv or os.path.join(HERE, f"bull_scan_{asof_str}.csv")
    rows = [{"ticker": t, "asof": asof_str, "quintile": p.get("quintile"),
             "composite": p.get("comp"), "close": p["close"], "distPct": round(p["distPct"], 2),
             "rsi": round(p["rsi"], 1), "adx": round(p["adx"], 1), "stop": p["stop"],
             "t1": p["t1"], "t2": p["t2"], "size": p["size"], "signals": "|".join(p["signals"])}
            for t, p in hits]
    pd.DataFrame(rows, columns=["ticker", "asof", "quintile", "composite", "close", "distPct",
                                "rsi", "adx", "stop", "t1", "t2", "size", "signals"]).to_csv(csv_path, index=False)
    print(f"\n  saved {os.path.basename(csv_path)}\n")
    import housekeeping
    housekeeping.retain_newest(os.path.join(HERE, "bull_scan_*.csv"), keep=30)


if __name__ == "__main__":
    main()
