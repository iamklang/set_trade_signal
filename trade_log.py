#!/usr/bin/env python3
"""
trade_log.py — persistent ledger of actual trade executions.

The daily pipeline (scan_dip → positions.json) tracks what the SYSTEM recommends.
This module tracks what the USER actually did: real fill prices, real sizes, real
exits. Stored in trade_log.json alongside the plan-snapshot so the quarterly
review can compare plan vs actual.

trade_log.json is the sole source of truth for actual executions; positions.json
remains the system-signal state managed by scan_dip.py (this module never writes
to positions.json).
"""
import json
import os
from datetime import date, datetime

import costs

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(HERE, "trade_log.json")

OPEN = "open"
CLOSED = "closed"
CANCELLED = "cancelled"

EXIT_REASONS = ("STOP", "TRAIL", "BE", "T1", "MANUAL")


def load(path=DEFAULT_PATH):
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict) or "trades" not in data:
            return {"version": 1, "trades": []}
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"version": 1, "trades": []}


def save(data, path=DEFAULT_PATH):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _num(x):
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def next_id(trades, ticker, entry_date):
    """Generate 'YYYYMMDD-TICKER-seq' id."""
    base_ticker = ticker.replace(".BK", "")
    date_str = entry_date.replace("-", "")
    prefix = f"{date_str}-{base_ticker}"
    existing = [t["id"] for t in trades if t["id"].startswith(prefix)]
    seq = len(existing) + 1
    return f"{prefix}-{seq}"


def _validate_add(fields):
    errors = []
    if not fields.get("ticker"):
        errors.append("ticker is required")
    if not fields.get("entry_date"):
        errors.append("entry_date is required")
    entry_price = _num(fields.get("entry_price"))
    if entry_price is None or entry_price <= 0:
        errors.append("entry_price must be > 0")
    entry_size = _num(fields.get("entry_size"))
    if entry_size is None or entry_size <= 0:
        errors.append("entry_size must be > 0")
    if errors:
        raise ValueError("; ".join(errors))


def _validate_close(fields):
    errors = []
    if not fields.get("exit_date"):
        errors.append("exit_date is required")
    exit_price = _num(fields.get("exit_price"))
    if exit_price is None or exit_price <= 0:
        errors.append("exit_price must be > 0")
    reason = fields.get("exit_reason")
    if reason and reason not in EXIT_REASONS:
        errors.append(f"exit_reason must be one of {EXIT_REASONS}")
    if errors:
        raise ValueError("; ".join(errors))


def _ensure_bk(ticker):
    if ticker and not ticker.endswith(".BK"):
        return ticker + ".BK"
    return ticker


def _quarter_of(d):
    if not d:
        return None
    y, m = int(d[:4]), int(d[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"


def add_trade(data, fields):
    """Add a new trade to the ledger. Returns the assigned ID."""
    _validate_add(fields)
    ticker = _ensure_bk(fields["ticker"])
    entry_date = fields["entry_date"]
    trade_id = next_id(data["trades"], ticker, entry_date)
    now = _now_iso()

    trade = {
        "id": trade_id,
        "ticker": ticker,
        "quarter": _quarter_of(entry_date),
        "status": OPEN,

        "plan_date": fields.get("plan_date"),
        "plan_signal": fields.get("plan_signal"),
        "plan_buy": _num(fields.get("plan_buy")),
        "plan_stop": _num(fields.get("plan_stop")),
        "plan_t1": _num(fields.get("plan_t1")),
        "plan_size": _num(fields.get("plan_size")),
        "plan_quintile": _num(fields.get("plan_quintile")),

        "entry_date": entry_date,
        "entry_price": _num(fields["entry_price"]),
        "entry_size": int(_num(fields["entry_size"])),

        "exit_date": None,
        "exit_price": None,
        "exit_reason": None,

        "is_dw": bool(fields.get("is_dw", False)),
        "dw_series": fields.get("dw_series"),
        "notes": fields.get("notes", ""),
        "created_at": now,
        "updated_at": now,
    }
    data["trades"].append(trade)
    return trade_id


def _find(data, trade_id):
    for t in data["trades"]:
        if t["id"] == trade_id:
            return t
    raise KeyError(f"trade '{trade_id}' not found")


def update_trade(data, trade_id, updates):
    """Partial update of a trade record."""
    trade = _find(data, trade_id)
    forbidden = {"id", "created_at"}
    for k, v in updates.items():
        if k in forbidden:
            continue
        trade[k] = v
    trade["updated_at"] = _now_iso()
    return trade


def close_trade(data, trade_id, exit_date, exit_price, exit_reason, notes=None):
    """Mark a trade as closed with exit details."""
    fields = {"exit_date": exit_date, "exit_price": exit_price, "exit_reason": exit_reason}
    _validate_close(fields)
    trade = _find(data, trade_id)
    if trade["status"] != OPEN:
        raise ValueError(f"trade '{trade_id}' is {trade['status']}, not open")
    if exit_date < trade["entry_date"]:
        raise ValueError("exit_date cannot be before entry_date")
    trade["status"] = CLOSED
    trade["exit_date"] = exit_date
    trade["exit_price"] = _num(exit_price)
    trade["exit_reason"] = exit_reason
    if notes is not None:
        trade["notes"] = notes
    trade["updated_at"] = _now_iso()
    return trade


def cancel_trade(data, trade_id):
    """Mark a trade as cancelled."""
    trade = _find(data, trade_id)
    trade["status"] = CANCELLED
    trade["updated_at"] = _now_iso()
    return trade


def open_trades(data):
    return [t for t in data["trades"] if t["status"] == OPEN]


def closed_trades(data, quarter=None):
    trades = [t for t in data["trades"] if t["status"] == CLOSED]
    if quarter:
        trades = [t for t in trades if t.get("quarter") == quarter]
    return trades


def trade_pl(trade, gross=False):
    """Compute P/L for a single trade. Returns dict with pl_pct, pl_baht, or None if incomplete."""
    entry = _num(trade.get("entry_price"))
    exit_px = _num(trade.get("exit_price"))
    size = _num(trade.get("entry_size"))
    if not entry or not exit_px or not size:
        return None
    gross_frac = (exit_px - entry) / entry
    cost_frac = 0.0 if gross else (costs.side_cost(entry) + costs.side_cost(exit_px))
    net_frac = gross_frac - cost_frac
    return {
        "pl_pct": round(net_frac * 100, 2),
        "pl_baht": round(net_frac * entry * size, 0),
        "gross_pct": round(gross_frac * 100, 2),
        "cost_pct": round(cost_frac * 100, 2),
    }


def plan_vs_actual(trade):
    """Deviation metrics between plan and actual execution."""
    result = {}
    entry = _num(trade.get("entry_price"))
    plan_buy = _num(trade.get("plan_buy"))
    if entry and plan_buy:
        result["entry_slippage_pct"] = round((entry - plan_buy) / plan_buy * 100, 2)

    actual_size = _num(trade.get("entry_size"))
    plan_size = _num(trade.get("plan_size"))
    if actual_size and plan_size:
        result["size_ratio"] = round(actual_size / plan_size, 2)

    exit_px = _num(trade.get("exit_price"))
    plan_stop = _num(trade.get("plan_stop"))
    if exit_px and entry and plan_stop and entry != plan_stop:
        result["actual_rr"] = round((exit_px - entry) / (entry - plan_stop), 2)

    plan_t1 = _num(trade.get("plan_t1"))
    if exit_px and plan_t1:
        result["reached_t1"] = exit_px >= plan_t1

    entry_date = trade.get("entry_date")
    exit_date = trade.get("exit_date")
    if entry_date and exit_date:
        result["hold_days"] = (date.fromisoformat(exit_date) - date.fromisoformat(entry_date)).days

    result["is_planned"] = trade.get("plan_date") is not None
    return result


def actual_metrics(trades):
    """Compute the same 4 Q-Close metrics as quarterly_review.metrics() on actual trade data."""
    import quarterly_review as qrev
    formatted = []
    for t in trades:
        pl = trade_pl(t)
        if pl is None:
            continue
        formatted.append({
            "ticker": t["ticker"],
            "entry_date": t["entry_date"],
            "exit_date": t["exit_date"],
            "entry": _num(t["entry_price"]),
            "exit": _num(t["exit_price"]),
            "size": _num(t["entry_size"]),
            "reason": t.get("exit_reason"),
            "quintile": _num(t.get("plan_quintile")),
            "signals": [t["plan_signal"]] if t.get("plan_signal") else ["manual"],
            "pl_pct": pl["pl_pct"],
            "pl_baht": pl["pl_baht"],
        })
    m = qrev.metrics(formatted)
    a = qrev.signal_attribution(formatted)
    return {"metrics": m, "attribution": a}


def comparison_summary(data, quarter=None):
    """Summary stats for plan-vs-actual across all closed trades in a quarter."""
    trades = closed_trades(data, quarter)
    if not trades:
        return None
    comparisons = [plan_vs_actual(t) for t in trades]
    planned = [c for c in comparisons if c.get("is_planned")]
    slippages = [c["entry_slippage_pct"] for c in planned if "entry_slippage_pct" in c]
    rrs = [c["actual_rr"] for c in planned if "actual_rr" in c]
    t1_hits = [c for c in planned if c.get("reached_t1")]

    return {
        "total_trades": len(trades),
        "planned_trades": len(planned),
        "unplanned_trades": len(trades) - len(planned),
        "avg_slippage_pct": round(sum(slippages) / len(slippages), 2) if slippages else None,
        "avg_actual_rr": round(sum(rrs) / len(rrs), 2) if rrs else None,
        "t1_hit_rate": round(len(t1_hits) / len(planned) * 100, 1) if planned else None,
    }
