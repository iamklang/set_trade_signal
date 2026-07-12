#!/usr/bin/env python3
"""
scan_dip.py — daily "BUY (dip)" scanner for a SET universe.

Evaluates the set-dw-swing BUY(dip) signal (setdw_signal.buy_signal, identical to
set-dw-swing.pine defaults) on the most recent bar for every ticker in a universe
file, and prints the names that fired with their entry/stop/target/size plan.

Usage:
    ~/.venvs/trading-dr/bin/python scan_dip.py        # SET100, today, 1% risk
    python scan_dip.py --asof 2025-03-14 --sort dist  # spot-check a past date
    python scan_dip.py --universe my.txt --equity 500000 --risk 1.5

This is a CANDIDATE list only — the macro/sector/earnings judgment and DW selection
(SKILL.md §1–§4b) are still applied by hand. Yahoo data is EOD/delayed: run after close.
"""
import argparse
import glob
import os
import re
import sys
import time
from datetime import date, datetime

import numpy as np
import pandas as pd
import yfinance as yf

import setdw_signal as sig
import bullish_signals as bull
import set_data
import profiles
import costs


def prune_scan_dupes(here):
    """Keep only the newest dip_scan_*.csv per scan-date; delete older same-date duplicates
    (repeated same-day runs add nothing — still-holdable dedups by ticker). Returns count removed."""
    by_date = {}
    for f in glob.glob(os.path.join(here, "dip_scan_*.csv")):
        m = re.search(r"dip_scan_(\d{4}-\d{2}-\d{2})", os.path.basename(f))
        if m:
            by_date.setdefault(m.group(1), []).append(f)
    removed = 0
    for fs in by_date.values():
        if len(fs) > 1:
            fs.sort(key=os.path.getmtime)
            for old in fs[:-1]:
                try:
                    os.remove(old); removed += 1
                except OSError:
                    pass
    return removed

try:
    import exchange_calendars as xcals
    _CAL = xcals.get_calendar("XBKK")
except Exception:
    _CAL = None


def check_trading_day(requested: date) -> tuple[bool, date]:
    """Return (is_session, prev_session). Falls back gracefully if calendar unavailable."""
    if _CAL is None:
        return True, requested
    ts = pd.Timestamp(requested)
    is_sess = _CAL.is_session(ts)
    if is_sess:
        prev = _CAL.previous_session(ts).date()
    else:
        prev = _CAL.date_to_session(ts, direction="previous").date()
    return is_sess, prev


def parse_args():
    p = argparse.ArgumentParser(description="SET BUY(dip) scanner")
    p.add_argument("--universe", default="set100.bk.txt", help="ticker file (one .BK per line)")
    p.add_argument("--equity", type=float, default=100_000, help="account equity (THB)")
    p.add_argument("--risk", type=float, default=1.0, help="risk per trade (percent)")
    p.add_argument("--rsi", type=int, default=sig.RSI_MIN, help="RSI(14) minimum")
    p.add_argument("--adx", type=int, default=sig.ADX_MIN, help="ADX(14) minimum")
    p.add_argument("--maxext", type=float, default=0.0, help="cap %% above EMA (0=off; backtest says keep OFF)")
    p.add_argument("--no-profile", action="store_true",
                   help="ignore per-stock profiles.py overrides (use the global --rsi for all)")
    p.add_argument("--novol", action="store_true", help="disable the volume>average filter (ON by default)")
    p.add_argument("--asof", default=None, help="evaluate signal as of YYYY-MM-DD (default: latest bar)")
    p.add_argument("--source", default="yahoo", choices=["set", "yahoo"],
                   help="price data source (default: yahoo — batch, real OHLC, no WAF; "
                        "'set' = official SET via Playwright/WAF, ~1yr history only)")
    p.add_argument("--concurrency", type=int, default=6,
                   help="SET parallel fetch workers (default 6; lower if WAF re-challenges)")
    p.add_argument("--cache-hours", type=float, default=0,
                   help="reuse data/<SYM>.csv if younger than N hours (0=always fresh)")
    p.add_argument("--entry", default="dip_or_brk", choices=["dip", "dip_or_brk"],
                   help="entry signal: dip (original BUY dip only) or dip_or_brk "
                        "(dip OR breakout — bt_weekly proved PF 1.96 Q1 vs 1.33 dip-only, default)")
    p.add_argument("--sort", default="adx", choices=["adx", "dist", "rsi"], help="sort key (desc)")
    p.add_argument("--composite", action="store_true",
                   help="rank the universe by the cross-sectional composite factor "
                        "(momentum+trend+low-vol) and tag each dip hit with its quintile")
    p.add_argument("--leaders-only", action="store_true",
                   help="with --composite: keep ONLY dip hits in the top quintile (trend leaders)")
    p.add_argument("--comp-weights", default="1,1,0",
                   help="composite mom,trend,lowvol[,quality] weights (default 1,1,0 — SET100 "
                        "walk-forward says mom+trend is the best price-only blend; add a 4th value "
                        ">0 to fetch SET ROE and blend the quality/q-factor, e.g. 1,1,0,0.5)")
    p.add_argument("--rank-max-age-days", type=float, default=3,
                   help="with --composite: reuse composite_rank.csv if younger than N days "
                        "instead of re-pulling Yahoo (12-1 momentum barely moves daily; 0=always recompute)")
    p.add_argument("--period", default="2y", help="yfinance history window (warms SMA200/Wilder)")
    p.add_argument("--csv", default=None, help="CSV output path (default: dip_scan_<date>.csv)")
    p.add_argument("--max-positions", type=int, default=12,
                   help="cap concurrent managed holdings, keeping the strongest by composite "
                        "(needs --composite for the ranking; 0=uncapped). Default 12.")
    p.add_argument("--no-regime-brake", action="store_true",
                   help="disable the market-regime brake (default ON: halve position size when "
                        "the equal-weight SET index is below its 200-SMA = risk-off).")
    p.add_argument("--min-turnover", type=float, default=10e6,
                   help="liquidity gate (THB/day trailing median): drop BUY(dip) hits below this. "
                        "Default 10M — a bt_portfolio cost study showed thin names' wide (2-tick) "
                        "spreads kill the edge; a LIGHT gate helps, a heavy one over-filters. 0=off.")
    return p.parse_args()


def load_universe(path):
    out = []
    try:
        with open(path) as f:
            for line in f:
                t = line.split("#")[0].strip()
                if t:
                    out.append(t)
    except FileNotFoundError:
        sys.exit(f"universe file not found: {path}")
    if not out:
        sys.exit(f"universe file empty: {path}")
    return out


def book_equity(here, fallback_equity):
    """(equity_now, peak) for the ddbrake leg of the exposure overlay. equity_now = quarter.json
    start_equity + this quarter's P/L (realized closed + open unrealized, reconstructed by
    quarterly_review from git history); peak is carried in market_regime.json and ratcheted up.
    Degrades to (start_equity, start_equity) — ddbrake off, factor 1.0 — whenever quarter.json or
    the git reconstruction is unavailable, so a data/repo gap never brakes sizing."""
    import json as _json
    start_eq = fallback_equity
    try:
        with open(os.path.join(here, "quarter.json")) as f:
            start_eq = float(_json.load(f).get("start_equity") or fallback_equity)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    equity_now = start_eq
    try:
        import quarterly_review as qrev
        snaps = qrev.snapshots()
        if snaps:
            q = qrev.quarter_of(snaps[-1][0])
            closed = [t for t in qrev.closed_trades(snaps)
                      if t["exit_date"] and qrev.quarter_of(t["exit_date"]) == q]
            opens = qrev.open_positions(snaps)
            equity_now = start_eq + sum(t["pl_baht"] for t in closed) + sum(o["pl_baht"] for o in opens)
    except Exception:
        equity_now = start_eq
    prev_peak = start_eq
    try:
        with open(os.path.join(here, "market_regime.json")) as f:
            prev_peak = float(_json.load(f).get("peak") or start_eq)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return round(equity_now, 2), round(max(prev_peak, equity_now, start_eq), 2)


def main():
    a = parse_args()
    cfg = {"rsi_min": a.rsi, "adx_min": a.adx, "maxext": a.maxext,
           "need_vol_conf": not a.novol}
    entry_sigs = ["dip"] if a.entry == "dip" else ["dip", "breakout"]
    tickers = load_universe(a.universe)
    today = date.today()
    requested_date = date.fromisoformat(a.asof) if a.asof else today
    is_session, prev_session = check_trading_day(requested_date)

    if not is_session:
        print(f"\n  ⚠ {requested_date} is not a SET trading day "
              f"({'weekend' if requested_date.weekday() >= 5 else 'SET holiday'}).")
        print(f"    Showing signals for last session: {prev_session}\n")
        requested_date = prev_session
    elif requested_date == today and _CAL is not None:
        # Warn if market hasn't closed yet (SET closes 16:35 ICT = 09:35 UTC)
        import datetime as _dt
        utc_now = _dt.datetime.now(_dt.timezone.utc).time()
        if utc_now < _dt.time(9, 35):
            print(f"\n  ⚠ SET market may still be open (closes 16:35 ICT / 09:35 UTC)."
                  f" Data could be partial — re-run after close.\n")

    asof = pd.Timestamp(requested_date)

    hits, missing, stale, asof_date = [], [], [], None

    def run_scan(fetch):
        # Pass 1: slice every frame to <= asof and find the scan bar = the LATEST last-bar
        # date across the universe. Names whose own last bar is older (halted / SP / Yahoo
        # lag) are evaluated on a DIFFERENT day's bar — silently mixing dates made a stale
        # name's day-old candle look like "today's signal". They are excluded from fresh
        # BUY hits (reported as stale); the positions book still sees their frames.
        nonlocal asof_date
        sliced = {}
        for t in tickers:
            df = fetch(t)
            if df is None or len(df) < sig.SMA_LEN + 30:
                missing.append((t, "insufficient history")); continue
            if asof is not None:
                df = df[df.index <= asof]
                if len(df) < sig.SMA_LEN + 30:
                    missing.append((t, "no data before asof")); continue
            sliced[t] = df
        if not sliced:
            return
        last_bar = {t: df.index[-1].date() for t, df in sliced.items()}
        asof_date = max(last_bar.values())
        # Pass 2: evaluate the signal only on names whose last bar IS the scan bar.
        for t, df in sliced.items():
            if last_bar[t] != asof_date:
                stale.append((t, last_bar[t])); continue
            try:
                cfg_t = cfg if a.no_profile else profiles.cfg_for(t, cfg)
                d = bull.add_signals(df, cfg_t)
                row = d.iloc[-1]
                fired = [s for s in entry_sigs if bool(row.get(s))]
                if fired:
                    plan = sig.trade_plan(row, a.equity, a.risk)
                    plan["signals"] = fired
                    hits.append((t, plan))
            except Exception as e:
                missing.append((t, str(e)[:40]))

    if a.source == "set":
        # one browser / one WAF session, all names fetched concurrently up front
        frames = set_data.fetch_all(tickers, concurrency=a.concurrency,
                                    cache_hours=a.cache_hours)
    else:
        frames = set_data.fetch_yahoo_all(tickers, period=a.period)   # one batch call, no WAF
    run_scan(lambda t: frames.get(t))

    asof_str = (asof_date or datetime.now().date()).isoformat()

    # Liquidity gate: drop BUY(dip) hits on thin names (trailing turnover below --min-turnover).
    # A bt_portfolio cost study (costs.py / medallion-research) found thin names' wide 2-tick
    # spreads kill the edge; a LIGHT ฿-floor helps net-of-cost, a heavy one over-filters. Applied
    # before composite tagging + positions so both the scan output and the managed book skip them.
    dropped_thin = []
    if a.min_turnover and a.min_turnover > 0:
        kept = []
        for t, pl in hits:
            tv = costs.trailing_turnover(frames.get(t), asof=(asof if a.asof else None))
            if tv is not None and tv < a.min_turnover:
                dropped_thin.append((t, tv))
            else:
                kept.append((t, pl))
        hits = kept

    # Combo EXPOSURE OVERLAY (voltgt × ddbrake) — the robust replacement for the old regime brake
    # (bt_portfolio 2026-07-12 sweep: combo lifts Sharpe on 10y/5y/tickliq and cuts maxDD, where
    # the plain index<200-SMA regime brake failed the 5y OOS test). voltgt de-risks when the tape
    # is hot; ddbrake halves new sizing when the book is >12% off its equity peak. Default ON;
    # --no-regime-brake disables (regime_mult stays 1.0). Skip the book (ddbrake) leg for --asof
    # historical scans, where today's live book doesn't reflect that date.
    _here0 = os.path.dirname(os.path.abspath(__file__))
    if a.asof:
        equity_now, peak = None, None
    else:
        equity_now, peak = book_equity(_here0, a.equity)
    exp = sig.exposure_overlay(frames, equity_now=equity_now, peak=peak,
                               asof=(asof if a.asof else None))
    regime_mult = 1.0 if a.no_regime_brake else exp["factor"]

    # Cross-sectional composite ranking (optional) — tag hits with quintile/rank and,
    # with --leaders-only, keep just the top-quintile trend leaders. The composite needs
    # ~12mo+ of history for 12-1 momentum; SET data serves only ~1yr, so when the dip
    # source is SET we rank off a separate Yahoo pull (long history) instead.
    comp, comp_fresh = None, False
    rank_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "composite_rank.csv")
    if a.composite:
        import composite as comp_mod
        # Reuse a still-fresh ranking file instead of re-pulling Yahoo for 100 names daily —
        # 12-1 momentum is a 12-month signal that barely moves day to day (see --rank-max-age-days).
        if a.rank_max_age_days > 0 and not a.asof and os.path.exists(rank_path):
            age_d = (time.time() - os.path.getmtime(rank_path)) / 86400
            if age_d <= a.rank_max_age_days:
                try:
                    comp = pd.read_csv(rank_path).set_index("ticker")
                    comp_fresh = True
                    print(f"  composite: reusing {os.path.basename(rank_path)} "
                          f"({age_d:.1f}d old ≤ {a.rank_max_age_days:g}d, no Yahoo pull)")
                except Exception:
                    comp = None
        if comp is None:                # (re)compute the ranking
            cw = [float(x) for x in a.comp_weights.split(",")]
            while len(cw) < 4:
                cw.append(0.0)
            weights = {"mom": cw[0], "trend": cw[1], "lowvol": cw[2], "quality": cw[3]}
            comp_frames = frames if a.source == "yahoo" else set_data.fetch_yahoo_all(tickers, period=a.period)
            quality = None
            if weights["quality"] > 0:      # opt-in: fetch SET ROE for the quality factor
                try:
                    qf = set_data.fetch_fundamentals(tickers, concurrency=a.concurrency)
                    quality = {t: (qf.get(t) or {}).get("roe") for t in tickers}
                    nq = sum(1 for v in quality.values() if v is not None)
                    print(f"  quality: ROE fetched for {nq}/{len(tickers)} names")
                except Exception as e:
                    print(f"  [warn] quality fetch failed ({str(e)[:50]}) — dropping quality factor")
            comp = comp_mod.cross_section_scores(
                comp_frames, asof=(asof if a.asof else None), weights=weights, quality=quality)
            if comp.empty:
                print("\n  ⚠ composite ranking empty (insufficient history) — skipping filter.\n")
                comp = None

        if comp is not None and not comp.empty:
            for t, p in hits:
                p["comp"] = round(float(comp.loc[t, "composite"]), 3) if t in comp.index else None
                q = int(comp.loc[t, "quintile"]) if t in comp.index else None
                # Composite-quintile size tilt (Q1 1.5× … Q5 0.5×) × combo exposure overlay
                sig.apply_size_tilt(p, q, regime_mult)
            if a.leaders_only:
                hits = [(t, p) for t, p in hits if p.get("quintile") == 1]
        if comp is not None and not comp.empty and not comp_fresh:
            # Persist the freshly-computed ranking so alert.py / scan_bull can tag leaders
            # without re-fetching (skip when we just reused the existing file).
            out = comp.reset_index().rename(columns={"index": "ticker"})
            keep = ["ticker", "composite", "rank", "quintile", "mom", "trend"]
            if "quality" in out.columns:
                keep.append("quality")
            out = out[keep].copy()
            out.insert(1, "asof", asof_str)
            out.round(4).to_csv(rank_path, index=False)
            print(f"  saved composite ranking -> {os.path.basename(rank_path)} "
                  f"({len(out)} names)")

    # Apply the exposure overlay even without --composite (no quintile info, so tilt is neutral
    # but the combo ×factor still applies); with --composite it was already folded in above.
    if comp is None and regime_mult != 1.0:
        for _, p in hits:
            sig.apply_size_tilt(p, None, regime_mult)

    # Persist the exposure overlay for alert.py to apply the same brake to its watchlist fires +
    # display. `factor` stays the field name every reader (alert.py, load_market_regime) expects.
    try:
        import json as _json
        with open(os.path.join(_here0, "market_regime.json"), "w") as _rf:
            _json.dump({"asof": asof_str, "factor": regime_mult,
                        "voltgt": exp["voltgt"], "ddbrake": exp["ddbrake"],
                        "mkt_vol": exp["mkt_vol"], "dd": exp["dd"],
                        "equity": equity_now, "peak": peak,
                        "risk_off": exp["risk_off"], "index": exp["index"], "sma": exp["sma"],
                        "brake_enabled": not a.no_regime_brake}, _rf, indent=2)
    except OSError:
        pass

    # Sort
    keymap = {"adx": lambda x: x[1]["adx"], "dist": lambda x: x[1]["distPct"], "rsi": lambda x: x[1]["rsi"]}
    hits.sort(key=keymap[a.sort], reverse=True)

    # Report
    entry_lbl = "dip" if a.entry == "dip" else "dip|brk"
    print(f"\nSET DW Swing — BUY({entry_lbl}) scan | src {a.source} | as of {asof_str} | universe {a.universe} "
          f"({len(tickers)} names) | RSI>={a.rsi} ADX>={a.adx}"
          + ("" if a.novol else " vol>avg")
          + (f" maxExt={a.maxext}%" if a.maxext else "")
          + ("" if a.no_profile else f" | profiles {','.join(profiles.PROFILES)}")
          + (f" | composite {a.comp_weights}" + (" leaders-only" if a.leaders_only else "")
             if comp is not None else "") + "\n")

    if exp["mkt_vol"] is not None and regime_mult < 1.0 and not a.no_regime_brake:
        bits = []
        if exp["voltgt"] < 1.0:
            bits.append(f"voltgt ×{exp['voltgt']} (mkt vol {exp['mkt_vol']*100:.0f}% > "
                        f"target {sig.TARGET_VOL*100:.0f}%)")
        if exp["ddbrake"] < 1.0:
            bits.append(f"ddbrake ×{exp['ddbrake']} (book {exp['dd']*100:+.0f}% off peak)")
        print(f"  ⚠ EXPOSURE BRAKE: size ×{regime_mult} — " + "; ".join(bits) + "\n")
    elif exp["mkt_vol"] is not None and exp["voltgt"] < 1.0 and a.no_regime_brake:
        print(f"  ⚠ market vol {exp['mkt_vol']*100:.0f}% > target but --no-regime-brake "
              f"→ size NOT braked\n")

    if comp is not None:
        print(f"  Top composite leaders (weights mom,trend,lowvol={a.comp_weights}, Q1=top quintile):")
        lead = comp.head(10)
        print(f"    {'ticker':12s}{'comp':>7s}{'Q':>3s}{'mom%':>8s}{'trnd%':>7s}{'vol%':>7s}")
        for t, r in lead.iterrows():
            volv = r.get("lowvol")          # absent when reusing composite_rank.csv (not stored)
            vol_s = f"{-float(volv)*100:>7.0f}" if volv is not None and pd.notna(volv) else f"{'-':>7s}"
            print(f"    {t:12s}{r['composite']:>7.2f}{int(r['quintile']):>3d}"
                  f"{r['mom']*100:>8.0f}{r['trend']*100:>7.1f}{vol_s}")
        print()

    if not hits:
        print(f"  no BUY({entry_lbl}) signals today.\n")
    else:
        qcol = f"{'Q':>3s}" if comp is not None else ""
        sigcol = "  sig" if a.entry != "dip" else ""
        hdr = (f"{'ticker':12s}{'close':>9s}{'dist%':>7s}{'RSI':>6s}{'ADX':>6s}"
               f"{'buy':>9s}{'stop':>9s}{'T1':>9s}{'T2':>9s}{'size':>9s}{qcol}{sigcol}")
        print(hdr); print("-" * len(hdr))
        for t, p in hits:
            q = f"{p.get('quintile'):>3d}" if comp is not None and p.get('quintile') else ("" if comp is None else f"{'-':>3s}")
            stag = "  " + "|".join(p.get("signals", [])) if a.entry != "dip" else ""
            print(f"{t:12s}{p['close']:>9.2f}{p['distPct']:>+7.1f}{p['rsi']:>6.0f}{p['adx']:>6.0f}"
                  f"{p['buy']:>9.2f}{p['stop']:>9.2f}{p['t1']:>9.2f}{p['t2']:>9.2f}{p['size']:>9,d}{q}{stag}")
        tag = " (top-quintile leaders)" if a.leaders_only else ""
        print(f"\n  {len(hits)} signal(s){tag}.  Watchlist: " + " ".join(t for t, _ in hits))
        print("  buy = ราคา limit ที่ควรตั้งซื้อวันถัดไป (ที่ราคานี้หรือดีกว่า — อย่าไล่ราคาที่ gap ขึ้น)")
        if comp is not None:
            print("  size = fixed-risk × composite-quintile tilt "
                  "(Q1 1.5× · Q2 1.25× · Q3 1× · Q4 0.75× · Q5 0.5×)")

    if dropped_thin:
        print(f"  ⏭ dropped thin (turnover < ฿{a.min_turnover/1e6:.0f}M/day, edge dies on wide spreads): "
              + ", ".join(f"{t.replace('.BK','')}(฿{tv/1e6:.0f}M)" for t, tv in dropped_thin))

    # ---- Stateful BUY/SELL managed watchlist (positions.json) --------------------
    # scan_dip is the SOLE writer: fold today's fresh BUY(dip) hits into the persistent
    # holdings list, flag any held name whose thesis broke (WEAK/STOP) to sell ONCE, and
    # drop names flagged on a prior run. alert.py reads this file for the LINE brief.
    import positions as pos
    pstate = pos.load()
    # Exits must see the bar we scanned, not "today": when --asof is set, slice each frame to
    # <= asof so a historical spot-check / walk evaluates holdings on the right bar. (No --asof
    # → latest bar is the intended one, pass frames through untouched.)
    pos_frames = ({t: df[df.index <= asof] for t, df in frames.items()}
                  if a.asof else frames)
    # Composite score drives the position cap (keep the strongest names when the book is full).
    ranks = ({t: float(comp.loc[t, "composite"]) for t in comp.index}
             if comp is not None and not comp.empty else None)
    cap = a.max_positions if a.max_positions and a.max_positions > 0 else None
    pstate, trans = pos.update(pstate, hits, pos_frames, asof_str,
                               ranks=ranks, max_positions=cap)
    # A historical spot-check must NEVER overwrite the live book: --asof advances the
    # lifecycle from TODAY's positions.json as if it were that past bar (mixed state),
    # so persist only when scanning the latest bar.
    if a.asof:
        print("\n  (--asof spot-check: positions.json NOT saved)")
    else:
        pos.save(pstate)

    def _nm(t):
        return str(t).replace(".BK", "")

    hold = trans["holding"]; t1_today = trans["t1_today"]
    sell_today = trans["sell_today"]; dropped = trans["dropped"]; skipped = trans["skipped"]
    capnote = f"cap {cap}" if cap else "uncapped"
    print(f"\n  === Managed watchlist (positions.json) — {len(hold)} holding "
          f"(let-run, {capnote}) ===")
    if hold:
        hh = f"    {'ticker':10s}{'entry':>8s}{'now':>8s}{'P/L':>7s}{'stat':>6s}{'since':>12s}"
        print(hh); print("    " + "-" * (len(hh) - 4))
        for r in hold:
            pl = f"{r['pl_pct']:+.1f}%" if r.get("pl_pct") is not None else "   n/a"
            tag = " *new" if r.get("new") else (" (วิ่ง)" if r.get("status") == "RUN" else "")
            print(f"    {_nm(r['ticker']):10s}{(r.get('entry_close') or 0):>8.2f}"
                  f"{(r.get('cur') or 0):>8.2f}{pl:>7s}{r.get('status','?'):>6s}"
                  f"{str(r.get('entry_date','')):>12s}{tag}")
    else:
        print("    (empty)")

    if t1_today:
        print("\n  🔵 ถึง T1 (เลื่อน stop มาทุน + ปล่อยวิ่ง, shown once):")
        for r in t1_today:
            pl = f"{r['pl_pct']:+.1f}%" if r.get("pl_pct") is not None else "n/a"
            print(f"    {_nm(r['ticker']):10s} entry {r.get('entry_close')} "
                  f"now {r.get('cur')} ({pl}) → {pos.t1_note()}")

    if sell_today:
        print("\n  🔴 ขาย (SELL flagged today, shown once):")
        for r in sell_today:
            pl = f"{r['pl_pct']:+.1f}%" if r.get("pl_pct") is not None else "n/a"
            print(f"    {_nm(r['ticker']):10s} {r.get('sell_reason','?'):6s} "
                  f"entry {r.get('entry_close')} now {r.get('cur')} ({pl}) "
                  f"→ {pos.sell_note(r.get('sell_reason'))}")

    if skipped:
        print(f"\n  ⏭ not added (book full of stronger composite names): "
              + ", ".join(_nm(t) for t in skipped))

    if dropped:
        print("\n  removed (was flagged SELL on a prior run): "
              + ", ".join(_nm(r["ticker"]) for r in dropped))

    if stale:
        print(f"\n  ⚠ stale data — last bar older than scan bar {asof_str}, excluded from "
              "BUY eval: " + ", ".join(f"{t.replace('.BK','')}({d})" for t, d in stale[:15])
              + ("…" if len(stale) > 15 else ""))

    if missing:
        print(f"\n  skipped {len(missing)} (no/short data): "
              + ", ".join(f"{t}" for t, _ in missing[:20]) + ("…" if len(missing) > 20 else ""))

    print("\n  ⚠ candidate list only — apply macro/sector/earnings judgment + DW selection "
          "(SKILL §1–§4b) before acting. Data is EOD; mechanical signal alone is ~break-even.\n")

    # CSV — include run timestamp so repeated scans don't overwrite
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if hits:
        csv_path = a.csv or f"dip_scan_{asof_str}_{run_ts}.csv"
        rows = [{"ticker": t, **{k: ("|".join(v) if k == "signals" and isinstance(v, list)
                                     else round(v, 4) if isinstance(v, float) else v)
                                 for k, v in p.items()}} for t, p in hits]
        pd.DataFrame(rows).to_csv(csv_path, index=False)
        print(f"  saved {csv_path}\n")
    else:
        csv_path = a.csv or f"dip_scan_{asof_str}_{run_ts}.csv"
        pd.DataFrame(columns=["ticker"]).iloc[:0].to_csv(csv_path, index=False)
        print(f"  saved {csv_path} (no signals)\n")

    # Housekeeping: one dip_scan CSV per date (drop same-day dupes) + keep only recent dates,
    # before validating.
    import housekeeping
    _here = os.path.dirname(os.path.abspath(__file__))
    pruned = prune_scan_dupes(_here)
    pruned += housekeeping.retain_newest(os.path.join(_here, "dip_scan_*.csv"), keep=40)
    if pruned:
        print(f"  pruned {pruned} old/duplicate scan file(s)")

    # Validate all scan CSVs (incremental — skips already-decided rows)
    import subprocess, sys
    print("  running validation on all scans...")
    subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "validate_scans.py"),
         "--source", a.source, "--cache-hours", str(max(a.cache_hours, 4))],
    )


if __name__ == "__main__":
    main()
