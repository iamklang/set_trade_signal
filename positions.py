#!/usr/bin/env python3
"""
positions.py — the stateful BUY/SELL managed watchlist for the SET DW Swing system.

Max-profit "let winners run" lifecycle (chosen 2026-07-03 from the bt_exits.py trade-level
study: V5 = breakeven-at-T1 + EMA-trail, NO T2 cap, was the highest PF 1.26 / +0.93%/trade,
1.34 / +1.33% with a Q1 filter — capping at T2 threw away the right tail). Each name:

  BUY(dip)         close>=T1 (+1R)                  close<EMA20 (after T1)  or  close<=stop
   │  enter FULL    │ stop -> breakeven, let it run   │ exit the whole position
   ▼                ▼                                 ▼
 HOLDING/FULL ───▶ HOLDING/RUN ─────────────────────▶ SELL_FLAGGED ──▶ dropped next run
   └─ close<=structural stop (before T1) ───────────▶ SELL_FLAGGED ──▶ dropped next run

There is NO close<EMA exit BEFORE T1 and no below-entry "WEAK" exit (those cut ~84% of
trades early and made the old list a net loser, PF 0.75). Above-EMA trailing only kicks in
AFTER +1R is locked at breakeven, so a whipsaw can't lose money. No fixed T2 cap — winners
run until they lose the EMA.

POSITION CAP: the book is held to `max_positions` of the strongest names by composite score
(mom+trend). When full, a weaker new dip hit is skipped; if the cap is exceeded, the lowest-
composite EXISTING holdings are rotated out ("ROTATE"). Ranking uses composite_rank.csv that
scan_dip --composite writes; without ranks the cap is not enforced.

State lives in positions.json (project root). scan_dip.py is the sole writer; alert.py reads it.
"""
import json
import os
from datetime import date

import setdw_signal as sig
import market

HERE = os.path.dirname(os.path.abspath(__file__))
# Resolved per active market at call time (SET → repo root; US → us/). Kept as a module
# attribute for back-compat, but load()/save() default to the live market path.
DEFAULT_PATH = os.path.join(HERE, "positions.json")


def _default_path():
    return market.state_path("positions.json")

HOLDING = "HOLDING"
SELL_FLAGGED = "SELL_FLAGGED"
FULL = "FULL"          # holding full size, before +1R
RUN = "RUN"            # +1R locked at breakeven, trailing the EMA, no upside cap

MAX_POSITIONS = 12     # default cap on concurrent holdings (keep the strongest by composite)

# Cooldown after a full exit, before the same name can re-enter — mirrors the 5-BAR cooldown
# every backtest (bt_exits.py, bt_portfolio.py) assumes when measuring the shipped edge. Without
# this, live can churn a stopped-out name back in on the very next signal, which the backtests
# never modeled (their reported PF/Sharpe implicitly assume this gap exists). Counted in XBKK
# TRADING SESSIONS (matching the backtests' bar unit — 5 calendar days spanning a weekend is
# only ~3 bars, which let live re-enter earlier than the measured edge); falls back to calendar
# days when exchange_calendars is unavailable.
COOLDOWN_BARS = 5
MIN_HOLD_BARS = 5      # minimum bars before a position can be rotated out
_COOLDOWN_KEY = "_cooldown"           # reserved top-level key: {ticker: date_last_dropped}

try:
    import exchange_calendars as _xcals
    _CAL = _xcals.get_calendar("XBKK")
except Exception:
    _CAL = None


def _days_since(then, now):
    return (date.fromisoformat(str(now)) - date.fromisoformat(str(then))).days


def _bars_since(then, now):
    """XBKK trading sessions strictly after `then`, up to and including `now` — the unit the
    backtests' 5-bar cooldown is measured in. Calendar-day fallback without the calendar."""
    if _CAL is not None:
        try:
            import pandas as _pd
            a, b = _pd.Timestamp(str(then)), _pd.Timestamp(str(now))
            if b <= a:
                return 0
            return int(_CAL.sessions_in_range(a + _pd.Timedelta(days=1), b).size)
        except Exception:
            pass
    return _days_since(then, now)


def _rotation_eligible(rec, asof_date):
    """A position can be rotated out only if it is not in profit AND has been held
    long enough.  Winners (P/L > 0) are protected so the right tail can develop;
    young positions (< MIN_HOLD_BARS) haven't had time to show their edge yet."""
    entry = rec.get("entry_date")
    if not entry or _bars_since(entry, asof_date) < MIN_HOLD_BARS:
        return False
    cur = rec.get("cur") or 0
    entry_px = rec.get("entry_close") or 0
    if entry_px and cur > entry_px:
        return False
    return True


def load(path=None):
    """Read positions.json -> {ticker: record}. Missing/corrupt file -> {}.
    path=None → the active market's positions.json (SET root / US us/)."""
    path = path or _default_path()
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save(positions, path=None):
    """Write positions.json (sorted keys, 2-space indent). path=None → active market."""
    path = path or _default_path()
    with open(path, "w") as f:
        json.dump(positions, f, indent=2, sort_keys=True, ensure_ascii=False)


def _r(x, nd=2):
    """Round to nd decimals, or None when missing/non-numeric."""
    if x is None:
        return None
    try:
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None


def _latest(df):
    """(close, ema20) on the latest bar, or (None, None) / (close, None) when short."""
    if df is None or len(df) < 1:
        return None, None
    try:
        close = float(df["Close"].iloc[-1])
    except (KeyError, IndexError, ValueError):
        return None, None
    ema = None
    if len(df) >= sig.EMA_LEN + 5:
        try:
            ema = float(sig.add_indicators(df)["ema"].iloc[-1])
        except Exception:
            ema = None
    return close, ema


# Re-anchor threshold: rescale stored levels when the entry bar's close in today's data has
# drifted more than this (relative) from the recorded entry_close. 0.25% sits well below any
# real SET dividend (~1-5%) but above float/rounding noise on 2dp prices.
ADJ_TOL = 0.0025


def _rescale_levels(rec, df):
    """Yahoo frames are dividend/split-adjusted (auto_adjust=True): after an XD every bar
    BEFORE the ex-date is scaled down retroactively, so price levels stored at entry sit on a
    stale scale — the post-XD close can breach the stored stop by the dividend gap alone, a
    false STOP the backtest (adjusted end-to-end) never sees. Re-anchor each run: compare
    today's adjusted close ON THE ENTRY BAR to the stored entry_close; if drifted beyond
    ADJ_TOL, scale every stored price level by that factor. Idempotent — entry_close is
    rewritten too, so the next run's factor ≈ 1. A missing entry bar leaves levels untouched."""
    entry, edate = rec.get("entry_close"), rec.get("entry_date")
    if not entry or not edate or df is None or len(df) == 0:
        return rec
    try:
        bar = df["Close"].loc[str(edate)]
        adj = float(bar.iloc[-1]) if hasattr(bar, "iloc") else float(bar)
    except (KeyError, TypeError, ValueError):
        return rec
    if not adj or adj <= 0:
        return rec
    factor = adj / float(entry)
    if abs(factor - 1.0) <= ADJ_TOL:
        return rec
    for k in ("entry_close", "stop", "init_stop", "t1", "t2"):
        v = rec.get(k)
        if v is not None:
            rec[k] = _r(float(v) * factor)
    return rec


def sell_note(reason):
    """Thai reason shown next to a fully-exited (SELL_FLAGGED) name."""
    return {
        "TRAIL": "หลุด EMA20 (หลัง T1) — ขายเก็บกำไร",
        "STOP": "หลุดสต็อป — ขายทั้งหมด",
        "BE": "กลับมาที่ทุน (breakeven) — ขาย เสมอตัว",
        "ROTATE": "สับเปลี่ยนออก — ตัวใหม่มี upside ดีกว่า",
    }.get(reason, "ขาย")


def t1_note():
    """Thai note for the one-time +1R event (moved stop to breakeven, now let it run)."""
    return "ถึง T1 — เลื่อน stop มาที่ทุน แล้วปล่อยวิ่ง (ไม่ cap กำไร)"


def _flag_sell(rec, reason, asof_date):
    rec["state"] = SELL_FLAGGED
    rec["status"] = reason
    rec["sell_reason"] = reason
    rec["flagged_date"] = asof_date


def update(positions, fresh_hits, frames, asof_date, ranks=None, max_positions=None):
    """Advance the let-winners-run lifecycle by one bar. Returns (positions, transitions).

    positions     : {ticker: record} loaded from positions.json
    fresh_hits    : list of (ticker, plan) confirmed BUY(dip) today (plan = trade_plan dict)
    frames        : {ticker: OHLCV df} — latest close+EMA20 drive the stop/T1/trail checks
    asof_date     : 'YYYY-MM-DD' of the evaluated (closed) bar
    ranks         : {ticker: composite_score} (higher=stronger) for the position cap; None=off
    max_positions : cap on concurrent holdings (keep the top-`ranks` names); None=uncapped

    transitions = {"holding":[…], "t1_today":[…], "sell_today":[…], "dropped":[…], "skipped":[…]}
      holding    = every name still held AFTER this run (buy list; FULL or RUN)
      t1_today   = names that hit +1R THIS run (stop->breakeven, now running) — show once
      sell_today = names fully exited THIS run (trail/stop/breakeven/rotate) — show once, drop next
      dropped    = names removed this run (were flagged on a prior run)
      skipped    = fresh hits not admitted — book full of stronger names, OR still on cooldown
                   (COOLDOWN_BARS trading sessions since a full exit; tickers, reason not distinguished)"""
    positions = {t: dict(r) for t, r in positions.items()}
    fired_today = {t for t, _ in fresh_hits}
    trans = {"holding": [], "t1_today": [], "sell_today": [], "dropped": [], "skipped": [],
             "over_cap": []}

    # 1) Drop names flagged on a PRIOR run ("remove next day") — starts their cooldown.
    cooldown = positions.get(_COOLDOWN_KEY, {})
    for t in list(positions):
        if t == _COOLDOWN_KEY:
            continue
        rec = positions[t]
        if rec.get("state") == SELL_FLAGGED and str(rec.get("flagged_date")) < asof_date:
            trans["dropped"].append({**rec, "ticker": t})
            del positions[t]
            cooldown[t] = asof_date
    # Purge cleared cooldowns so the ledger doesn't grow forever.
    cooldown = {t: d for t, d in cooldown.items() if _bars_since(d, asof_date) < COOLDOWN_BARS}
    if cooldown:
        positions[_COOLDOWN_KEY] = cooldown
    elif _COOLDOWN_KEY in positions:
        del positions[_COOLDOWN_KEY]

    # 2) Add fresh BUY(dip) hits -> HOLDING/FULL (new entry, or re-entry of a running/flagged
    #    name). An existing holding keeps its original plan; a re-entry resets it. A name still
    #    cooling down from a recent full exit is skipped (whipsaw guard matching the backtest's
    #    bar cooldown), not opened.
    added = set()
    for t, p in fresh_hits:
        ex = positions.get(t)
        if ex and ex.get("state") == HOLDING:
            ex["last_seen"] = asof_date
            continue
        # A signal the capital guard trimmed to 0 shares can't be a real position — don't
        # record a phantom size=0 holding that would occupy a slot in the ~12-name cap. It
        # will simply re-fire on a later scan once capital frees up (no cooldown consumed).
        if not p.get("size"):
            trans["skipped"].append(t)
            continue
        if t in cooldown and _bars_since(cooldown[t], asof_date) < COOLDOWN_BARS:
            trans["skipped"].append(t)
            continue
        cooldown.pop(t, None)
        positions[t] = {
            "state": HOLDING, "phase": FULL,
            "entry_date": asof_date, "entry_close": _r(p.get("close")),
            "stop": _r(p.get("stop")), "init_stop": _r(p.get("stop")),
            "t1": _r(p.get("t1")), "t2": _r(p.get("t2")),
            "rsi": _r(p.get("rsi"), 0), "adx": _r(p.get("adx"), 0),
            "size": p.get("size"), "size_mult": p.get("size_mult"),
            "regime_mult": p.get("regime_mult"), "quintile": p.get("quintile"),
            "signals": p.get("signals"),
            "first_seen": (ex or {}).get("first_seen", asof_date), "last_seen": asof_date,
            "t1_date": None, "flagged_date": None,
        }
        added.add(t)

    # 3) Exits. Precedence: stop (worst case) > T1 breakeven-move > EMA trail (only after T1).
    #    Names that fired BUY today are exempt (just (re)entered).
    for t in list(positions):
        if t == _COOLDOWN_KEY:
            continue
        rec = positions[t]
        if rec.get("state") != HOLDING:
            continue
        df_t = frames.get(t)
        _rescale_levels(rec, df_t)          # XD/split re-anchor BEFORE any stop/T1 comparison
        close, ema = _latest(df_t)
        entry, phase = rec.get("entry_close"), rec.get("phase", FULL)
        rec["cur"] = _r(close)
        rec["pl_pct"] = (_r((close - entry) / entry * 100, 1)
                         if close is not None and entry else None)
        rec["eff_stop"] = _r(max(rec.get("stop", 0), ema) if phase == RUN and ema else rec.get("stop"))
        rec["ema20"] = _r(ema)
        rec["opp_score"] = round(opportunity_score(rec), 4) if close is not None else None
        if close is None or t in fired_today:
            rec["status"] = RUN if phase == RUN else "HOLD"
            continue
        stop, t1 = rec.get("stop"), rec.get("t1")
        if stop is not None and close <= stop:
            _flag_sell(rec, "BE" if phase == RUN else "STOP", asof_date)
            trans["sell_today"].append({**rec, "ticker": t})
        elif phase == FULL and t1 is not None and close >= t1:
            rec["phase"] = RUN                # lock breakeven, let the winner run (no T2 cap)
            rec["stop"] = entry
            rec["t1_date"] = asof_date
            rec["status"] = RUN
            trans["t1_today"].append({**rec, "ticker": t})
        elif phase == RUN and ema is not None and close < ema:
            _flag_sell(rec, "TRAIL", asof_date)
            trans["sell_today"].append({**rec, "ticker": t})
        else:
            rec["status"] = RUN if phase == RUN else "HOLD"

    # 4) Position cap — hold only the strongest `max_positions` by composite + opportunity.
    #    A weak new entry is silently skipped; an over-cap EXISTING holding rotates out
    #    ONLY if it is rotation-eligible (not in profit, held long enough).
    if max_positions and ranks is not None:
        held = [t for t, r in positions.items()
                if isinstance(r, dict) and r.get("state") == HOLDING and t != _COOLDOWN_KEY]
        if len(held) > max_positions:
            held.sort(key=lambda t: (ranks.get(t, float("-inf")),
                                     opportunity_score(positions[t])), reverse=True)
            for t in held[max_positions:]:
                if t in added:
                    del positions[t]
                    trans["skipped"].append(t)
                elif _rotation_eligible(positions[t], asof_date):
                    _flag_sell(positions[t], "ROTATE", asof_date)
                    trans["sell_today"].append({**positions[t], "ticker": t})
            still_held = [t for t in held if t in positions and positions[t].get("state") == HOLDING]
            if len(still_held) > max_positions:
                protected = [t for t in still_held[max_positions:]
                             if not _rotation_eligible(positions[t], asof_date)]
                trans["over_cap"] = protected

    # 4b) Proactive rotation: even at cap (not over), swap the weakest incumbent if a new
    #     candidate has clearly better forward opportunity (upside to T1 > incumbent + 5%).
    #     Only rotation-eligible incumbents (not in profit, held long enough) can be swapped.
    OPP_THRESHOLD = 0.05
    if max_positions and ranks is not None:
        held_all = [t for t, r in positions.items()
                    if isinstance(r, dict) and r.get("state") == HOLDING and t != _COOLDOWN_KEY]
        new_entries = [t for t in added
                       if t in positions and positions[t].get("state") == HOLDING]
        if len(held_all) >= max_positions and new_entries:
            incumbents = {t: opportunity_score(positions[t])
                          for t in held_all
                          if t not in added and _rotation_eligible(positions[t], asof_date)}
            if incumbents:
                weakest_t = min(incumbents, key=incumbents.get)
                weakest_opp = incumbents[weakest_t]
                for t in new_entries:
                    new_opp = opportunity_score(positions[t])
                    if new_opp > weakest_opp + OPP_THRESHOLD:
                        _flag_sell(positions[weakest_t], "ROTATE", asof_date)
                        positions[weakest_t]["rotate_for"] = t
                        positions[weakest_t]["opp_diff"] = round(new_opp - weakest_opp, 4)
                        trans["sell_today"].append({**positions[weakest_t], "ticker": weakest_t})
                        break

    # 5) Build the surviving holdings bucket (after exits + cap).
    for t, rec in positions.items():
        if rec.get("state") == HOLDING:
            trans["holding"].append({**rec, "ticker": t, "new": t in added})
    _sort_holding(trans["holding"])
    return positions, trans


def opportunity_score(rec):
    """Forward-looking: remaining % gain to T1 (FULL) or EMA trail cushion (RUN)."""
    px = rec.get("cur") or rec.get("buy")
    t1 = rec.get("t1")
    if not px or not t1 or px <= 0:
        return 0.0
    if rec.get("phase") == RUN:
        ema = rec.get("ema20")
        return (px - ema) / px if ema and px > ema else 0.01
    return max(0, (t1 - px) / px)


def committed_capital(positions):
    """Sum of (entry_close * size) for all HOLDING positions — capital already deployed."""
    total = 0.0
    for t, rec in positions.items():
        if t == _COOLDOWN_KEY or not isinstance(rec, dict):
            continue
        if rec.get("state") == HOLDING:
            total += (rec.get("entry_close") or 0) * (rec.get("size") or 0)
    return round(total, 2)


def available_capital(positions, total_equity):
    """Capital available for new positions = total_equity - committed."""
    return round(max(0, total_equity - committed_capital(positions)), 2)


def _sort_holding(rows):
    """Best -> worst by live P/L (RUN winners float up via their positive P/L)."""
    rows.sort(key=lambda r: -(r.get("pl_pct") if r.get("pl_pct") is not None else -999))


def holding_view(positions, asof=None):
    """Reader split for alert.py (no state advance). Returns (holding, t1_today, sell_today).
    With `asof`, t1/sell are limited to events stamped on that bar (t1_date / flagged_date ==
    asof) so the LINE brief shows each exactly once, matching the scan run that wrote the file."""
    holding, t1, sell = [], [], []
    for t, rec in positions.items():
        if t == _COOLDOWN_KEY:
            continue                  # reserved bookkeeping entry, not a ticker record
        row = {**rec, "ticker": t, "new": False}
        if rec.get("state") == SELL_FLAGGED:
            if asof is None or str(rec.get("flagged_date")) == asof:
                sell.append(row)
        else:
            holding.append(row)
            if rec.get("phase") == RUN and asof and str(rec.get("t1_date")) == asof:
                t1.append(row)
    _sort_holding(holding)
    return holding, t1, sell
