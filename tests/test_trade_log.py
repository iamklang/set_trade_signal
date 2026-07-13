"""Tests for trade_log.py — actual trade execution ledger."""
import json
import os
import tempfile

import trade_log as tl


def _empty():
    return {"version": 1, "trades": []}


def _sample_fields(**overrides):
    base = {
        "ticker": "STECON.BK",
        "entry_date": "2026-07-14",
        "entry_price": 18.50,
        "entry_size": 1100,
        "plan_date": "2026-07-10",
        "plan_signal": "dip",
        "plan_buy": 18.70,
        "plan_stop": 17.40,
        "plan_t1": 20.00,
        "plan_size": 1150,
        "plan_quintile": 1,
    }
    base.update(overrides)
    return base


# ---- load / save roundtrip ----

def test_load_missing_file():
    data = tl.load("/nonexistent/path.json")
    assert data == {"version": 1, "trades": []}


def test_save_load_roundtrip():
    data = _empty()
    tl.add_trade(data, _sample_fields())
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name
    try:
        tl.save(data, path)
        loaded = tl.load(path)
        assert len(loaded["trades"]) == 1
        assert loaded["trades"][0]["ticker"] == "STECON.BK"
    finally:
        os.unlink(path)


# ---- ID generation ----

def test_next_id_format():
    tid = tl.next_id([], "STECON.BK", "2026-07-14")
    assert tid == "20260714-STECON-1"


def test_next_id_increments():
    trades = [{"id": "20260714-STECON-1"}, {"id": "20260714-STECON-2"}]
    tid = tl.next_id(trades, "STECON.BK", "2026-07-14")
    assert tid == "20260714-STECON-3"


def test_next_id_different_ticker():
    trades = [{"id": "20260714-STECON-1"}]
    tid = tl.next_id(trades, "AMATA.BK", "2026-07-14")
    assert tid == "20260714-AMATA-1"


# ---- add_trade ----

def test_add_trade_basic():
    data = _empty()
    tid = tl.add_trade(data, _sample_fields())
    assert tid == "20260714-STECON-1"
    assert len(data["trades"]) == 1
    t = data["trades"][0]
    assert t["status"] == "open"
    assert t["ticker"] == "STECON.BK"
    assert t["entry_price"] == 18.50
    assert t["plan_buy"] == 18.70
    assert t["quarter"] == "2026Q3"


def test_add_trade_auto_appends_bk():
    data = _empty()
    tl.add_trade(data, _sample_fields(ticker="AMATA"))
    assert data["trades"][0]["ticker"] == "AMATA.BK"


def test_add_trade_unplanned():
    data = _empty()
    tl.add_trade(data, _sample_fields(plan_date=None, plan_signal=None))
    t = data["trades"][0]
    assert t["plan_date"] is None


def test_add_trade_validation_missing_ticker():
    data = _empty()
    try:
        tl.add_trade(data, _sample_fields(ticker=""))
        assert False, "should raise"
    except ValueError as e:
        assert "ticker" in str(e)


def test_add_trade_validation_bad_price():
    data = _empty()
    try:
        tl.add_trade(data, _sample_fields(entry_price=-1))
        assert False, "should raise"
    except ValueError as e:
        assert "entry_price" in str(e)


def test_add_trade_validation_bad_size():
    data = _empty()
    try:
        tl.add_trade(data, _sample_fields(entry_size=0))
        assert False, "should raise"
    except ValueError as e:
        assert "entry_size" in str(e)


# ---- close_trade ----

def test_close_trade():
    data = _empty()
    tid = tl.add_trade(data, _sample_fields())
    tl.close_trade(data, tid, "2026-08-01", 20.10, "TRAIL")
    t = data["trades"][0]
    assert t["status"] == "closed"
    assert t["exit_price"] == 20.10
    assert t["exit_reason"] == "TRAIL"


def test_close_trade_bad_reason():
    data = _empty()
    tid = tl.add_trade(data, _sample_fields())
    try:
        tl.close_trade(data, tid, "2026-08-01", 20.10, "INVALID")
        assert False, "should raise"
    except ValueError as e:
        assert "exit_reason" in str(e)


def test_close_trade_exit_before_entry():
    data = _empty()
    tid = tl.add_trade(data, _sample_fields())
    try:
        tl.close_trade(data, tid, "2026-07-01", 20.10, "TRAIL")
        assert False, "should raise"
    except ValueError as e:
        assert "exit_date" in str(e)


def test_close_already_closed():
    data = _empty()
    tid = tl.add_trade(data, _sample_fields())
    tl.close_trade(data, tid, "2026-08-01", 20.10, "TRAIL")
    try:
        tl.close_trade(data, tid, "2026-08-02", 21.00, "T1")
        assert False, "should raise"
    except ValueError as e:
        assert "not open" in str(e)


# ---- cancel_trade ----

def test_cancel_trade():
    data = _empty()
    tid = tl.add_trade(data, _sample_fields())
    tl.cancel_trade(data, tid)
    assert data["trades"][0]["status"] == "cancelled"


# ---- filters ----

def test_open_trades():
    data = _empty()
    tl.add_trade(data, _sample_fields())
    tl.add_trade(data, _sample_fields(ticker="AMATA", entry_date="2026-07-15"))
    tid = data["trades"][0]["id"]
    tl.close_trade(data, tid, "2026-08-01", 20.10, "TRAIL")
    assert len(tl.open_trades(data)) == 1
    assert tl.open_trades(data)[0]["ticker"] == "AMATA.BK"


def test_closed_trades_quarter_filter():
    data = _empty()
    tl.add_trade(data, _sample_fields(entry_date="2026-07-14"))
    tl.add_trade(data, _sample_fields(ticker="AMATA", entry_date="2026-04-01"))
    tl.close_trade(data, data["trades"][0]["id"], "2026-08-01", 20.10, "TRAIL")
    tl.close_trade(data, data["trades"][1]["id"], "2026-05-15", 30.00, "T1")
    assert len(tl.closed_trades(data, "2026Q3")) == 1
    assert len(tl.closed_trades(data, "2026Q2")) == 1
    assert len(tl.closed_trades(data)) == 2


# ---- P/L ----

def test_trade_pl_net():
    data = _empty()
    tl.add_trade(data, _sample_fields())
    tl.close_trade(data, data["trades"][0]["id"], "2026-08-01", 20.10, "TRAIL")
    pl = tl.trade_pl(data["trades"][0])
    assert pl is not None
    assert pl["gross_pct"] > 0
    assert pl["pl_pct"] < pl["gross_pct"]  # net < gross due to costs
    assert pl["cost_pct"] > 0
    assert pl["pl_baht"] > 0


def test_trade_pl_loss():
    data = _empty()
    tl.add_trade(data, _sample_fields())
    tl.close_trade(data, data["trades"][0]["id"], "2026-07-20", 17.40, "STOP")
    pl = tl.trade_pl(data["trades"][0])
    assert pl["pl_pct"] < 0
    assert pl["pl_baht"] < 0


def test_trade_pl_open_returns_none():
    data = _empty()
    tl.add_trade(data, _sample_fields())
    pl = tl.trade_pl(data["trades"][0])
    assert pl is None


# ---- plan vs actual ----

def test_plan_vs_actual_slippage():
    data = _empty()
    tl.add_trade(data, _sample_fields())
    tl.close_trade(data, data["trades"][0]["id"], "2026-08-01", 20.10, "TRAIL")
    pva = tl.plan_vs_actual(data["trades"][0])
    assert pva["entry_slippage_pct"] < 0  # actual 18.50 < plan 18.70 = negative (better)
    assert pva["is_planned"] is True
    assert pva["reached_t1"] is True  # exit 20.10 >= T1 20.00
    assert pva["actual_rr"] > 0
    assert pva["hold_days"] == 18


def test_plan_vs_actual_unplanned():
    data = _empty()
    tl.add_trade(data, _sample_fields(plan_date=None, plan_buy=None))
    pva = tl.plan_vs_actual(data["trades"][0])
    assert pva["is_planned"] is False
    assert "entry_slippage_pct" not in pva


def test_plan_vs_actual_size_ratio():
    data = _empty()
    tl.add_trade(data, _sample_fields(entry_size=1000, plan_size=1150))
    pva = tl.plan_vs_actual(data["trades"][0])
    assert pva["size_ratio"] == round(1000 / 1150, 2)


# ---- comparison summary ----

def test_comparison_summary_empty():
    data = _empty()
    assert tl.comparison_summary(data) is None


def test_comparison_summary():
    data = _empty()
    tl.add_trade(data, _sample_fields())
    tl.close_trade(data, data["trades"][0]["id"], "2026-08-01", 20.10, "TRAIL")
    tl.add_trade(data, _sample_fields(ticker="AMATA", entry_date="2026-07-15",
                                       entry_price=28.50, entry_size=400,
                                       plan_buy=28.50, plan_stop=25.25, plan_t1=31.75))
    tl.close_trade(data, data["trades"][1]["id"], "2026-07-25", 25.00, "STOP")
    summary = tl.comparison_summary(data, "2026Q3")
    assert summary["total_trades"] == 2
    assert summary["planned_trades"] == 2
    assert summary["avg_slippage_pct"] is not None
    assert summary["t1_hit_rate"] is not None
