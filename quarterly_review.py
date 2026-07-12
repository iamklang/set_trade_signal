#!/usr/bin/env python3
"""
quarterly_review.py — the Q-Close review for the Medallion-style quarterly cadence.

Core concept (2026-07-12): the book is a systematic positive-expectancy machine reviewed by
QUARTER (≈63 trading days ≈ 3 hold cycles), not by week. This tool produces the four Q-Close
numbers that feed the next Q-Open:

  1) Expectancy      per-trade edge = winrate·avgWin − lossrate·avgLoss  (%, and ฿)
  2) Profit Factor   Σ winning ฿ / Σ |losing ฿|
  3) Signal attribution   dip vs breakout — which entry actually makes the money
  4) Max drawdown    peak-to-trough of the realized equity curve (฿ and %)

WHERE THE HISTORY COMES FROM: there is no trade ledger — positions.py drops a SELL_FLAGGED name
on the next run, so a closed trade leaves positions.json entirely. The authoritative record is the
GIT HISTORY of positions.json: daily_scan commits one snapshot per trading bar, so every state
transition (entry → SELL_FLAGGED → dropped) is captured. We reconstruct closed trades by walking
those blobs: a closed trade is the first snapshot in which a (ticker, entry_date) reaches
SELL_FLAGGED — that record carries entry_close, the exit price (`cur`), pl_pct, sell_reason,
quintile, size and signals. P/L is taken NET of the SET round-trip cost (costs.side_cost).

Usage:
    python quarterly_review.py                 # current quarter (of the latest snapshot)
    python quarterly_review.py --quarter 2026Q3
    python quarterly_review.py --all           # every closed trade, all quarters
    python quarterly_review.py --gross         # skip the cost model (gross P/L)
    python quarterly_review.py --json          # machine-readable dump
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import costs

POS_FILE = "positions.json"
_COOLDOWN_KEY = "_cooldown"


# ---------------------------------------------------------------- git history

def _git(*args):
    return subprocess.run(["git", "-C", HERE, *args],
                          capture_output=True, text=True, check=True).stdout


def snapshots():
    """[(commit_date 'YYYY-MM-DD', {ticker: rec})] for positions.json, oldest → newest.
    Includes the working-tree copy last if it differs from HEAD (so an un-committed
    same-day run is still reviewed)."""
    out = []
    log = _git("log", "--reverse", "--format=%H|%cd", "--date=short", "--", POS_FILE)
    for line in log.splitlines():
        if not line.strip():
            continue
        h, d = line.split("|", 1)
        try:
            blob = _git("show", f"{h}:{POS_FILE}")
            out.append((d, json.loads(blob)))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
    # working tree (may hold today's un-committed snapshot)
    path = os.path.join(HERE, POS_FILE)
    if os.path.exists(path):
        try:
            with open(path) as f:
                wt = json.load(f)
            if not out or out[-1][1] != wt:
                asof = max((r.get("last_seen") or r.get("entry_date") or ""
                            for k, r in wt.items()
                            if k != _COOLDOWN_KEY and isinstance(r, dict)), default="") \
                    or (out[-1][0] if out else "")
                out.append((asof, wt))
        except (json.JSONDecodeError, OSError):
            pass
    return out


# ---------------------------------------------------------------- reconstruction

def _rt_cost_frac(entry, exit_px, gross):
    """SET round-trip cost as a P/L fraction (entry side + exit side). gross=True → 0."""
    if gross or not entry or not exit_px:
        return 0.0
    return costs.side_cost(entry) + costs.side_cost(exit_px)


def closed_trades(snaps, gross=False):
    """Reconstruct realized trades from the snapshot timeline. A trade closes the first time a
    (ticker, entry_date) shows state SELL_FLAGGED. Returns list of trade dicts (net of costs)."""
    seen = set()
    trades = []
    for asof, book in snaps:
        for t, rec in book.items():
            if t == _COOLDOWN_KEY or not isinstance(rec, dict):
                continue
            if rec.get("state") != "SELL_FLAGGED":
                continue
            key = (t, rec.get("entry_date"))
            if key in seen:
                continue
            seen.add(key)
            entry = _num(rec.get("entry_close"))
            exit_px = _num(rec.get("cur")) or entry
            size = _num(rec.get("size")) or 0
            gross_frac = ((exit_px - entry) / entry) if entry else 0.0
            net_frac = gross_frac - _rt_cost_frac(entry, exit_px, gross)
            trades.append({
                "ticker": t,
                "entry_date": rec.get("entry_date"),
                "exit_date": rec.get("flagged_date") or asof,
                "entry": entry, "exit": exit_px, "size": size,
                "reason": rec.get("sell_reason") or rec.get("status"),
                "quintile": rec.get("quintile"),
                "signals": rec.get("signals") or ["dip"],
                "pl_pct": round(net_frac * 100, 2),
                "pl_baht": round(net_frac * entry * size, 0) if entry and size else 0.0,
            })
    return trades


def open_positions(snaps, gross=False):
    """Currently-held names from the latest snapshot, with unrealized (mark-to-market) P/L."""
    if not snaps:
        return []
    _, book = snaps[-1]
    out = []
    for t, rec in book.items():
        if t == _COOLDOWN_KEY or not isinstance(rec, dict):
            continue
        if rec.get("state") != "HOLDING":
            continue
        entry = _num(rec.get("entry_close"))
        cur = _num(rec.get("cur")) or entry
        size = _num(rec.get("size")) or 0
        gross_frac = ((cur - entry) / entry) if entry else 0.0
        net_frac = gross_frac - _rt_cost_frac(entry, cur, gross)
        out.append({
            "ticker": t, "entry_date": rec.get("entry_date"),
            "phase": rec.get("phase"), "quintile": rec.get("quintile"),
            "signals": rec.get("signals") or ["dip"],
            "pl_pct": round(net_frac * 100, 2),
            "pl_baht": round(net_frac * entry * size, 0) if entry and size else 0.0,
        })
    out.sort(key=lambda r: -(r["pl_pct"]))
    return out


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- metrics

def quarter_of(d):
    """'YYYY-MM-DD' → 'YYYYQn'."""
    y, m = int(d[:4]), int(d[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"


def _pf(wins, losses):
    """Profit factor from ฿ sums. +inf if only wins, 0 if only losses, None if no trades."""
    w = sum(t["pl_baht"] for t in wins)
    l = -sum(t["pl_baht"] for t in losses)
    if not wins and not losses:
        return None
    if l <= 0:
        return float("inf") if w > 0 else None
    return w / l


def metrics(trades):
    """The four Q-Close numbers for a set of closed trades (order-independent except drawdown)."""
    n = len(trades)
    if n == 0:
        return {"n": 0}
    wins = [t for t in trades if t["pl_baht"] > 0]
    losses = [t for t in trades if t["pl_baht"] < 0]
    flat = [t for t in trades if t["pl_baht"] == 0]
    winrate = len(wins) / n
    lossrate = len(losses) / n
    avg_win_pct = sum(t["pl_pct"] for t in wins) / len(wins) if wins else 0.0
    avg_loss_pct = sum(t["pl_pct"] for t in losses) / len(losses) if losses else 0.0  # negative

    # 4) max drawdown over the realized equity curve (ordered by exit date)
    eq, peak, mdd, mdd_pct = 0.0, 0.0, 0.0, 0.0
    for t in sorted(trades, key=lambda r: (r["exit_date"] or "", r["ticker"])):
        eq += t["pl_baht"]
        peak = max(peak, eq)
        dd = eq - peak
        if dd < mdd:
            mdd = dd
            mdd_pct = (dd / peak * 100) if peak > 0 else 0.0

    return {
        "n": n, "wins": len(wins), "losses": len(losses), "flat": len(flat),
        "winrate": winrate,
        "expectancy_pct": winrate * avg_win_pct + lossrate * avg_loss_pct,
        "expectancy_baht": sum(t["pl_baht"] for t in trades) / n,
        "avg_win_pct": avg_win_pct, "avg_loss_pct": avg_loss_pct,
        "profit_factor": _pf(wins, losses),
        "total_baht": sum(t["pl_baht"] for t in trades),
        "max_dd_baht": mdd, "max_dd_pct": mdd_pct,
    }


def signal_attribution(trades):
    """Group closed trades by their entry-signal tag (dip / breakout / dip|breakout)."""
    groups = {}
    for t in trades:
        tag = "|".join(t["signals"]) if t["signals"] else "dip"
        groups.setdefault(tag, []).append(t)
    return {tag: metrics(ts) for tag, ts in sorted(groups.items())}


# ---------------------------------------------------------------- risk budget

def load_budget():
    """Read quarter.json (the Q-Open risk budget), or None if absent/corrupt."""
    path = os.path.join(HERE, "quarter.json")
    try:
        with open(path) as f:
            b = json.load(f)
        return b if isinstance(b, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def budget_status(budget, trades, opens):
    """Live drawdown check against the quarter's budget. Current P/L = realized (closed this
    quarter) + unrealized (open, mark-to-market); drawdown is that as a % of start_equity."""
    realized = sum(t["pl_baht"] for t in trades)
    unrealized = sum(o["pl_baht"] for o in opens)
    total = realized + unrealized
    eq = float(budget.get("start_equity") or 0)
    dd_pct = (total / eq * 100) if eq > 0 else 0.0
    limit = float(budget.get("max_drawdown_pct") or 0)
    breached = limit > 0 and dd_pct <= -limit
    return {"realized": realized, "unrealized": unrealized, "total": total,
            "dd_pct": dd_pct, "limit": limit, "breached": breached}


# ---------------------------------------------------------------- reporting

def _fmt_pf(pf):
    if pf is None:
        return "  -  "
    if pf == float("inf"):
        return "  ∞  "
    return f"{pf:5.2f}"


def _fmt_baht(x):
    return f"{x:+,.0f}"


def print_report(quarter, trades, opens, cost_label, budget=None):
    print(f"\n{'='*66}")
    print(f"  Q-CLOSE REVIEW — {quarter}   (P/L {cost_label})")
    print(f"{'='*66}\n")

    if budget and budget.get("quarter") == quarter:
        bs = budget_status(budget, trades, opens)
        print(f"  RISK BUDGET (Q-Open {budget.get('start_date','')})")
        print(f"       equity {float(budget.get('start_equity',0)):,.0f} ฿  |  "
              f"risk {budget.get('risk_per_trade_pct','?')}%/ไม้  |  "
              f"max {budget.get('max_positions','?')} ตัว  |  "
              f"DD limit -{budget.get('max_drawdown_pct','?')}%")
        gauge = "🔴 BREACH — ลด size ครึ่ง (regime brake)" if bs["breached"] else "🟢 within budget"
        print(f"       P/L ไตรมาส {_fmt_baht(bs['total'])} ฿  "
              f"(realized {_fmt_baht(bs['realized'])} + open {_fmt_baht(bs['unrealized'])})  "
              f"= {bs['dd_pct']:+.2f}%   {gauge}")
        print()

    m = metrics(trades)
    if m["n"] == 0:
        print(f"  ยังไม่มี trade ที่ปิดในไตรมาสนี้ (0 closed trades).")
        print(f"  ระบบเพิ่งเริ่ม — เก็บสถิติต่อไป แล้ว metrics จะมีค่าเมื่อมีไม้ปิดจริง.\n")
    else:
        print(f"  ① EXPECTANCY (edge/ไม้)")
        print(f"       {m['expectancy_pct']:+.2f}% ต่อไม้   ({_fmt_baht(m['expectancy_baht'])} ฿/ไม้)")
        print(f"       winrate {m['winrate']*100:.0f}%  |  avg win {m['avg_win_pct']:+.2f}%"
              f"  avg loss {m['avg_loss_pct']:+.2f}%")
        print()
        print(f"  ② PROFIT FACTOR")
        print(f"       {_fmt_pf(m['profit_factor']).strip()}   (Σwin / Σloss, เป้า ≥ 1.9)")
        print(f"       รวม {m['n']} ไม้: {m['wins']}W / {m['losses']}L / {m['flat']}=  "
              f"→ {_fmt_baht(m['total_baht'])} ฿")
        print()
        print(f"  ③ SIGNAL ATTRIBUTION (dip vs breakout)")
        print(f"       {'signal':<14}{'n':>3} {'win%':>6} {'PF':>7} {'exp%':>7} {'฿':>12}")
        for tag, sm in signal_attribution(trades).items():
            print(f"       {tag:<14}{sm['n']:>3} {sm['winrate']*100:>5.0f}% "
                  f"{_fmt_pf(sm['profit_factor']):>7} {sm['expectancy_pct']:>+6.2f}% "
                  f"{_fmt_baht(sm['total_baht']):>12}")
        print()
        print(f"  ④ MAX DRAWDOWN")
        print(f"       {_fmt_baht(m['max_dd_baht'])} ฿  ({m['max_dd_pct']:+.1f}% ของ peak)")
        print()
        print(f"  {'-'*62}")
        print(f"  closed trades:")
        print(f"    {'ticker':<12}{'entry→exit':<24}{'reason':<8}{'sig':<10}{'P/L%':>7}{'฿':>12}")
        for t in sorted(trades, key=lambda r: r["exit_date"] or ""):
            nm = t["ticker"].replace(".BK", "")
            span = f"{t['entry_date']}→{t['exit_date']}"
            sig = "|".join(t["signals"])[:9]
            print(f"    {nm:<12}{span:<24}{(t['reason'] or ''):<8}{sig:<10}"
                  f"{t['pl_pct']:>+6.2f}%{_fmt_baht(t['pl_baht']):>12}")
        print()

    # open book context
    if opens:
        unreal = sum(o["pl_baht"] for o in opens)
        print(f"  {'-'*62}")
        print(f"  OPEN ({len(opens)}) — unrealized {_fmt_baht(unreal)} ฿ (mark-to-market):")
        for o in opens:
            nm = o["ticker"].replace(".BK", "")
            q = f"Q{o['quintile']}" if o.get("quintile") else " -"
            sig = "|".join(o["signals"])[:9]
            print(f"    {nm:<12}{q:>3} {o['phase']:<5} {sig:<10}"
                  f"{o['pl_pct']:>+6.2f}%{_fmt_baht(o['pl_baht']):>12}")
        print()


def main():
    ap = argparse.ArgumentParser(description="Quarterly (Q-Close) review from positions.json git history")
    ap.add_argument("--quarter", help="YYYYQn (default: quarter of the latest snapshot)")
    ap.add_argument("--all", action="store_true", help="all closed trades, ignore quarter filter")
    ap.add_argument("--gross", action="store_true", help="gross P/L (skip SET cost model)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()

    snaps = snapshots()
    if not snaps:
        print("no positions.json history found (need git commits of positions.json).")
        return

    all_closed = closed_trades(snaps, gross=a.gross)
    opens = open_positions(snaps, gross=a.gross)
    budget = load_budget()

    latest_date = snaps[-1][0]
    quarter = "ALL" if a.all else (a.quarter or quarter_of(latest_date))
    trades = all_closed if a.all else [t for t in all_closed
                                       if t["exit_date"] and quarter_of(t["exit_date"]) == quarter]

    if a.json:
        print(json.dumps({
            "quarter": quarter, "cost": "gross" if a.gross else "net",
            "metrics": metrics(trades),
            "attribution": signal_attribution(trades),
            "budget": budget,
            "budget_status": (budget_status(budget, trades, opens)
                              if budget and budget.get("quarter") == quarter else None),
            "closed": trades, "open": opens,
        }, ensure_ascii=False, indent=2, default=lambda o: None if o == float("inf") else o))
        return

    print_report(quarter, trades, opens,
                 "gross" if a.gross else "net of SET costs", budget=budget)


if __name__ == "__main__":
    main()
