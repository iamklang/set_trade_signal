#!/usr/bin/env python3
"""
alert.py — daily BUY(dip) alert for a WATCHLIST of SET names.

Generalises the old single-symbol alert_kce.py: evaluates the confirmed BUY(dip)
trigger (setdw_signal.buy_signal — same logic as the scanner / .pine) on the latest
closed bar for every name in the watchlist, prints a per-name verdict (with why-not
reasons on a near-miss), and fires ONE summary macOS notification listing the names
that confirmed. Built to be run by launchd after the SET close (16:35 ICT); stdout is
captured to alert.log by the launchd plist.

Data comes from the official SET (set_data.fetch_all — one browser, names fetched
concurrently); `--source yahoo` falls back to yfinance.

Exit code: 0 = at least one name fired, 1 = none fired, 2 = error.

Usage:
    ~/.venvs/trading-dr/bin/python alert.py                 # watchlist.txt
    ~/.venvs/trading-dr/bin/python alert.py --symbols KCE.BK CCET.BK
    ~/.venvs/trading-dr/bin/python alert.py --asof 2026-06-24
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import time
from datetime import datetime

import pandas as pd
import yfinance as yf

import setdw_signal as sig
import set_data
import profiles
import line_notify
import housekeeping

try:
    import exchange_calendars as xcals
    _CAL = xcals.get_calendar("XBKK")       # SET trading calendar (for the staleness check)
except Exception:
    _CAL = None


def expected_last_session(now=None):
    """Most recent SET session whose 16:35 ICT close has passed as of `now` (a datetime, default
    now): POST-close on a session day -> today; PRE-close or a non-session day -> the prior
    session. This makes the staleness check correct for BOTH an evening (post-close) run — which
    should expect today's bar — and a morning (pre-open) run. None if the calendar is unavailable
    (check then no-ops). The machine runs in ICT (+07), so wall-clock == exchange time."""
    if _CAL is None:
        return None
    now = now or datetime.now()
    ts = pd.Timestamp(now.date())
    try:
        if _CAL.is_session(ts):
            if (now.hour, now.minute) >= (16, 35):
                return ts.date()                          # today's session has closed
            return _CAL.previous_session(ts).date()       # pre-close -> the prior session
        return _CAL.date_to_session(ts, direction="previous").date()
    except Exception:
        return None

HERE = os.path.dirname(os.path.abspath(__file__))
WATCHLIST = os.path.join(HERE, "watchlist.txt")
EQUITY = 1_000_000
RISK_PCT = 1.0
_SCAN_DATE_RE = re.compile(r"dip_scan_(\d{4}-\d{2}-\d{2})")
MAX_VALIDATED = 30          # cap rows in the LINE "validated" section


def load_validated_candidates(here, exclude=None, limit=MAX_VALIDATED):
    """Aggregate the rows still marked validated==True across every dip_scan_*.csv
    (these are prior-day BUY(dip) hits that validate_scans.py re-confirmed), keeping
    the most recent scan_date per ticker. `exclude` drops names already firing fresh
    today. Returns a list of dicts {ticker, scan_date, close, stop, t1, t2, rsi, adx}
    sorted newest scan_date first, truncated to `limit`."""
    exclude = exclude or set()
    best = {}
    for fpath in glob.glob(os.path.join(here, "dip_scan_*.csv")):
        m = _SCAN_DATE_RE.search(os.path.basename(fpath))
        if not m:
            continue
        scan_date = m.group(1)
        try:
            df = pd.read_csv(fpath)
        except Exception:
            continue
        if "validated" not in df.columns or "ticker" not in df.columns:
            continue
        for _, r in df.iterrows():
            if str(r.get("validated")) != "True":
                continue
            t = str(r["ticker"])
            if t in exclude:
                continue
            if t not in best or scan_date > best[t]["scan_date"]:
                best[t] = {
                    "ticker": t, "scan_date": scan_date,
                    "close": r.get("close"), "stop": r.get("stop"),
                    "t1": r.get("t1"), "t2": r.get("t2"),
                    "rsi": r.get("rsi"), "adx": r.get("adx"),
                }
    rows = sorted(best.values(), key=lambda x: x["scan_date"], reverse=True)
    return rows[:limit]


def load_composite_ranks(here, max_age_h=48):
    """Read composite_rank.csv (written by scan_dip --composite) -> ({ticker: quintile},
    age_hours). Quintile 1 = top-quintile mom+trend leader. Returns ({}, age|None) if the
    file is missing, older than max_age_h, or unreadable — the freshness guard stops a stale
    ranking from silently mislabelling leaders in the alert."""
    path = os.path.join(here, "composite_rank.csv")
    if not os.path.exists(path):
        return {}, None
    age_h = (time.time() - os.path.getmtime(path)) / 3600
    if max_age_h and age_h > max_age_h:
        return {}, age_h
    try:
        df = pd.read_csv(path)
        ranks = {str(r["ticker"]): int(r["quintile"])
                 for _, r in df.iterrows() if pd.notna(r.get("quintile"))}
    except Exception:
        return {}, age_h
    return ranks, age_h


def load_bull_section(here, max_age_h=12):
    """Read the bull-scan section written by scan_bull (bull_msg.txt) so the alert can fold it
    into one combined LINE brief. Returns '' if missing or older than max_age_h (stale)."""
    path = os.path.join(here, "bull_msg.txt")
    if not os.path.exists(path):
        return ""
    if max_age_h and (time.time() - os.path.getmtime(path)) / 3600 > max_age_h:
        return ""
    try:
        return open(path).read().strip()
    except OSError:
        return ""


# live_status / _num / STATUS_RANK now live in setdw_signal (single source of truth,
# also consumed by positions.py); alias them here so existing references keep working.
_STATUS_RANK = sig.STATUS_RANK
_num = sig._num
live_status = sig.live_status


def load_watchlist(path):
    out = []
    try:
        with open(path) as f:
            for line in f:
                t = line.split("#")[0].strip()
                if t:
                    out.append(t)
    except FileNotFoundError:
        sys.exit(f"watchlist not found: {path} (create it or pass --symbols)")
    if not out:
        sys.exit(f"watchlist empty: {path}")
    return out


def notify(title, msg):
    """Best-effort macOS desktop notification; never raises."""
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{msg}" with title "{title}" sound name "Glass"'],
            check=False, timeout=10)
    except Exception:
        pass


def evaluate(sym, df, equity, risk, asof=None):
    """Return (fired: bool, line: str, plan|None) for one symbol's latest bar."""
    if df is None or len(df) < sig.SMA_LEN + 30:
        return False, f"{sym:10s} | no/insufficient data", None
    if asof:
        df = df[df.index <= pd.Timestamp(asof)]
        if len(df) < sig.SMA_LEN + 30:
            return False, f"{sym:10s} | no data before {asof}", None
    df = sig.add_indicators(df)
    cfg = {"rsi_min": sig.RSI_MIN, "adx_min": sig.ADX_MIN,
           "maxext": 0.0, "need_vol_conf": True}
    cfg = profiles.cfg_for(sym, cfg)        # per-stock overrides (KBANK/KTB/DELTA @60)
    rsi_floor = cfg["rsi_min"]
    fired = bool(sig.buy_signal(df, cfg).iloc[-1])
    row = df.iloc[-1]
    bar = df.index[-1].date()
    close = float(row["Close"])

    if not fired:
        reasons = []
        if not (close > row["ema"] and row["emaUp"] and row["ema"] > row["sma"] and row["smaUp"]):
            reasons.append("not-uptrend")
        if not bool(row["green"]):
            reasons.append("not-green")
        if not (row["llLook"] <= row["ema"] * (1 + sig.PROX) and row["freshprior"]):
            reasons.append("no-fresh-dip")
        if row["rsi"] < rsi_floor:
            reasons.append(f"rsi {row['rsi']:.0f}<{rsi_floor}")
        if row["adx"] < sig.ADX_MIN:
            reasons.append(f"adx {row['adx']:.0f}<{sig.ADX_MIN}")
        if row["Volume"] <= row["volSma"]:
            reasons.append(f"vol {row['Volume']/1e6:.1f}M<avg {row['volSma']/1e6:.1f}M")
        return False, (f"{sym:10s} | bar {bar} close {close:.2f} | "
                       f"NO SIGNAL ({', '.join(reasons) or 'setup incomplete'})"), None

    p = sig.trade_plan(row, equity, risk)
    line = (f"{sym:10s} | bar {bar} close {close:.2f} | *** BUY(dip) *** "
            f"stop {p['stop']:.2f} T1 {p['t1']:.2f} T2 {p['t2']:.2f} size {p['size']:,} "
            f"| RSI {p['rsi']:.0f} ADX {p['adx']:.0f}")
    return True, line, p


def main():
    ap = argparse.ArgumentParser(description="SET watchlist BUY(dip) alert")
    ap.add_argument("--symbols", nargs="*", help="symbols to check (overrides watchlist.txt)")
    ap.add_argument("--watchlist", default=WATCHLIST, help="watchlist file (one .BK per line)")
    ap.add_argument("--equity", type=float, default=EQUITY)
    ap.add_argument("--risk", type=float, default=RISK_PCT)
    ap.add_argument("--source", default="yahoo", choices=["set", "yahoo"])
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--cache-hours", type=float, default=4,
                    help="reuse data/<SYM>.csv if younger than N h (default 4 — EOD bar is closed, "
                         "so it reuses the morning scan's fetch instead of re-hitting the WAF)")
    ap.add_argument("--asof", default=None, help="evaluate as of YYYY-MM-DD")
    ap.add_argument("--no-line", action="store_true", help="disable LINE notification")
    ap.add_argument("--leaders-only", action="store_true",
                    help="alert only on composite Q1 leaders (reads composite_rank.csv from "
                         "the scan job; without the file it warns and does not filter)")
    a = ap.parse_args()

    symbols = a.symbols or load_watchlist(a.watchlist)

    try:
        if a.source == "set":
            frames = set_data.fetch_all(symbols, concurrency=a.concurrency,
                                        cache_hours=a.cache_hours)
        else:
            frames = set_data.fetch_yahoo_all(symbols)
    except Exception as e:
        print(f"[ERROR] data fetch failed: {e}")
        return 2

    fired = []
    scan_date = a.asof or ""
    verdicts = {}                       # sym -> verdict line (computed once, reused for the log)
    usable = 0                          # symbols that had real data (for the failure check)
    for sym in symbols:
        ok, line, plan = evaluate(sym, frames.get(sym), a.equity, a.risk, a.asof)
        print(line)
        verdicts[sym] = line
        if "bar " in line:              # a real evaluated bar (not "no/insufficient data")
            usable += 1
        if not scan_date and "bar " in line:
            scan_date = line.split("bar ")[1].split(" ")[0]
        if ok:
            fired.append((sym, plan))

    # Health warnings pushed to LINE so a failed/stale morning run is never silent:
    #  - data failure: no symbol returned a usable bar (WAF 403 / fetch died / all short)
    #  - stale bar:    the evaluated bar is older than the last completed SET session
    #                  (SET posted late, an unexpected holiday, or the job ran too early)
    warnings = []
    if usable == 0:
        warnings.append("⚠ ดึงข้อมูลไม่ได้เลย — เช็ค WAF/เน็ต (ไม่มีแท่งให้ประเมิน)")
    elif not a.asof and scan_date:
        exp = expected_last_session(datetime.now())
        if exp and scan_date < exp.isoformat():
            warnings.append(f"⚠ ข้อมูลอาจเก่า: แท่งล่าสุด {scan_date} (คาดว่าควรเป็น {exp})")
    for w in warnings:
        print(f"  {w}")

    # Tag each fired signal with its composite quintile (from the morning scan job) and,
    # with --leaders-only, alert only on the top-quintile (Q1) trend leaders.
    ranks, rank_age = load_composite_ranks(HERE)
    # Market-regime brake written by the scan job (halve size when risk-off). A stale/missing
    # file must NOT silently trust an old factor forever (e.g. the scan job died) — it falls
    # back to 1.0 (no brake) and warns, same freshness contract as load_composite_ranks.
    regime_factor, regime_age = sig.load_market_regime(
        os.path.join(HERE, "market_regime.json"))
    if regime_age is None:
        print("\n  ⚠ market_regime.json missing — regime brake NOT applied (scan job hasn't run?)")
        warnings.append("⚠ ไม่พบ market_regime.json — regime brake ไม่ทำงาน (scan job รันหรือยัง?)")
    elif regime_age > 48:
        print(f"\n  ⚠ market_regime.json stale ({regime_age:.0f}h old) — regime brake NOT applied")
        warnings.append(f"⚠ market_regime.json เก่า ({regime_age:.0f}ชม.) — regime brake ไม่ทำงาน")
    elif regime_factor < 1.0:
        print(f"\n  ⚠ MARKET RISK-OFF → regime brake ON, position size ×{regime_factor}")
    for sym, plan in fired:
        # composite-quintile size tilt (Q1 1.5× … Q5 0.5×) × regime brake; sets quintile too
        sig.apply_size_tilt(plan, ranks.get(sym), regime_factor)
    if a.leaders_only:
        if ranks:
            before = len(fired)
            fired = [(s, p) for s, p in fired if p.get("quintile") == 1]
            print(f"\n  leaders-only: kept {len(fired)}/{before} BUY(dip) in composite Q1"
                  f"  [rank file {rank_age:.0f}h old]")
        else:
            print("\n  ⚠ --leaders-only but composite_rank.csv missing/stale — not filtering.")

    # Append results to a persistent log so each run is preserved
    log_dir = os.path.join(HERE, "logs")
    os.makedirs(log_dir, exist_ok=True)
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"alert_{run_ts}.log")
    with open(log_path, "w") as lf:
        lf.write(f"alert.py run at {datetime.now().isoformat()}\n")
        lf.write(f"source={a.source} symbols={','.join(symbols)}\n\n")
        for sym in symbols:
            lf.write(verdicts[sym] + "\n")
        if fired:
            lf.write(f"\n*** {len(fired)} BUY(dip): {', '.join(s for s, _ in fired)}\n")
        else:
            lf.write("\nno BUY(dip) signals.\n")
    print(f"  log saved: {log_path}")
    dropped = housekeeping.retain_newest(os.path.join(log_dir, "alert_*.log"), keep=30)
    if dropped:
        print(f"  retention: removed {dropped} old alert log(s)")

    if fired:
        names = ", ".join(s for s, _ in fired)
        notify("SET — BUY(dip) trigger", f"{len(fired)} fired: {names}")
        print(f"\n  *** {len(fired)} BUY(dip): {names}")
    else:
        print("\n  no BUY(dip) signals.")

    # Read the stateful managed watchlist written by the morning/EOD scan_dip run
    # (scan_dip is the sole writer of positions.json). We only DISPLAY it here — the live
    # cur/status fields were computed at scan time on the same closed bar, so no refetch.
    import positions as pos
    pstate = pos.load()
    holding, t1_today, sell_today = pos.holding_view(pstate, asof=scan_date or None)
    for r in holding + t1_today + sell_today:
        r["quintile"] = ranks.get(r["ticker"])
    if sell_today or t1_today or holding:
        print("\n  managed watchlist (positions.json, let-run):")
        for r in sell_today:
            print(f"    🔴 {r['ticker']:10s} SELL {r.get('sell_reason','?')} — {pos.sell_note(r.get('sell_reason'))}")
        for r in t1_today:
            print(f"    🔵 {r['ticker']:10s} T1 — {pos.t1_note()}")
        for r in holding:
            pl = f"{r['pl_pct']:+.1f}%" if r.get("pl_pct") is not None else "n/a"
            lead = " ★Q1" if r.get("quintile") == 1 else ""
            print(f"    {r['ticker']:10s} {r.get('status','?'):5s} "
                  f"entry {r.get('entry_close')} now {r.get('cur')} ({pl}){lead}")

    if not a.no_line:
        # ONE combined morning brief: health warnings → bull shortlist (from scan_bull) →
        # watchlist dip + managed holdings / T1 / sell. Sections join with blank lines.
        alert_msg = line_notify.format_alert_message(fired, scan_date=scan_date,
                                                     holding=holding, sell_today=sell_today,
                                                     t1_today=t1_today)
        sections = []
        if regime_factor < 1.0:
            sections.append(f"⚠ ตลาด RISK-OFF (index < 200-SMA) → ลดขนาดโพซิชัน ×{regime_factor}")
        if warnings:
            sections.append("\n".join(warnings))
        bull = load_bull_section(HERE)
        if bull:
            sections.append(bull)
        sections.append(alert_msg)
        combined = "\n\n".join(sections)
        if line_notify.send_line_push(combined):
            print(f"  LINE brief sent ({'with' if bull else 'no'} bull section).")
        else:
            print("  LINE notification skipped (no credentials or send failed).")

    return 0 if fired else 1


if __name__ == "__main__":
    sys.exit(main())
