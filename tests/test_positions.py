"""Tests for positions.py — the let-winners-run (V5) lifecycle + composite position cap."""
import pandas as pd

import positions as pos


def _df(last_close, ema=None, n=30):
    """Frame whose latest Close is `last_close`. If `ema` given, bias the series so the
    computed EMA20 sits near it (only the sign of close-vs-EMA matters for the trail)."""
    if ema is None:
        closes = [last_close] * n
    else:
        # flat at `ema` then jump to last_close on the final bar -> EMA≈ema, close=last_close
        closes = [ema] * (n - 1) + [last_close]
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes,
                         "Close": closes, "Volume": [1_000_000] * n}, index=idx)


# entry 10, stop 9 (risk 1) -> T1=11, T2=11.5
def _hit(ticker, close=10.0, stop=9.0, t1=11.0, t2=11.5):
    return (ticker, {"close": close, "stop": stop, "t1": t1, "t2": t2,
                     "rsi": 60, "adx": 25, "size": 1000, "distPct": -0.5})


def _fr(px, ema=None):
    return {"X.BK": _df(px, ema)}


def test_fresh_buy_enters_full():
    state, tr = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    assert state["X.BK"]["phase"] == "FULL"
    assert [r["ticker"] for r in tr["holding"]] == ["X.BK"]
    assert tr["holding"][0]["status"] == "HOLD" and tr["holding"][0]["new"] is True
    assert not tr["t1_today"] and not tr["sell_today"]


def test_no_early_exit_below_entry_above_stop():
    """No WEAK/EMA exit before T1: drifting below entry but above stop must HOLD."""
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    state, tr = pos.update(state, [], _fr(9.5, ema=9.9), "2026-07-02")  # below entry & EMA, above stop
    assert state["X.BK"]["state"] == "HOLDING" and state["X.BK"]["phase"] == "FULL"
    assert tr["holding"][0]["status"] == "HOLD"
    assert not tr["sell_today"]


def test_t1_moves_to_breakeven_and_runs():
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    state, tr = pos.update(state, [], _fr(11.0), "2026-07-02")   # hits T1
    assert state["X.BK"]["phase"] == "RUN"
    assert state["X.BK"]["stop"] == 10.0                          # breakeven = entry
    assert state["X.BK"]["t1_date"] == "2026-07-02"
    assert [r["ticker"] for r in tr["t1_today"]] == ["X.BK"]
    assert not tr["sell_today"]


def test_run_has_no_t2_cap():
    """A running winner keeps running well past the old T2 (11.5) as long as it holds EMA."""
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    state, _ = pos.update(state, [], _fr(11.0), "2026-07-02")     # -> RUN
    state, tr = pos.update(state, [], _fr(13.0, ema=12.0), "2026-07-03")  # far above T2, above EMA
    assert state["X.BK"]["state"] == "HOLDING" and state["X.BK"]["phase"] == "RUN"
    assert tr["holding"][0]["status"] == "RUN"
    assert not tr["sell_today"]


def test_run_exits_on_ema_trail():
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    state, _ = pos.update(state, [], _fr(11.0), "2026-07-02")     # -> RUN, stop=10
    # close 11.2 (above breakeven 10, so not a BE stop) but below a risen EMA of 11.5 -> TRAIL
    state, tr = pos.update(state, [], _fr(11.2, ema=11.5), "2026-07-03")
    assert state["X.BK"]["sell_reason"] == "TRAIL"
    assert [r["ticker"] for r in tr["sell_today"]] == ["X.BK"]


def test_run_exits_at_breakeven():
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    state, _ = pos.update(state, [], _fr(11.0), "2026-07-02")     # -> RUN, stop=10
    state, tr = pos.update(state, [], _fr(10.0), "2026-07-03")    # back to breakeven
    assert state["X.BK"]["sell_reason"] == "BE"
    assert tr["sell_today"][0]["ticker"] == "X.BK"


def test_full_stops_out_before_t1():
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    state, tr = pos.update(state, [], _fr(8.9), "2026-07-02")     # below stop 9
    assert state["X.BK"]["sell_reason"] == "STOP"
    assert [r["ticker"] for r in tr["sell_today"]] == ["X.BK"]


def test_sell_shown_once_then_dropped():
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    state, tr = pos.update(state, [], _fr(8.9), "2026-07-02")     # STOP flagged
    assert tr["sell_today"] and not tr["dropped"]
    state, tr = pos.update(state, [], _fr(8.9), "2026-07-03")     # next run -> dropped
    assert "X.BK" not in state
    assert [r["ticker"] for r in tr["dropped"]] == ["X.BK"]


def test_fired_today_exempt_from_exit():
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    state["X.BK"]["stop"] = 12.0                                  # would STOP...
    state, tr = pos.update(state, [_hit("X.BK")], _fr(10.0), "2026-07-02")  # ...but re-fires
    assert state["X.BK"]["state"] == "HOLDING"
    assert not tr["sell_today"]


# ---- cooldown after a full exit (matches the backtests' 5-bar cooldown) -------------------

def test_dropped_name_skipped_during_cooldown():
    """A name re-firing right after being dropped is SKIPPED, not re-entered — mirrors the
    5-bar cooldown bt_exits.py/bt_portfolio.py assume when measuring the shipped edge."""
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    state, _ = pos.update(state, [], _fr(8.9), "2026-07-02")          # STOP flagged
    state, tr = pos.update(state, [], _fr(8.9), "2026-07-03")         # dropped, cooldown starts
    assert "X.BK" not in state
    # re-fires the very next session — still cooling down (COOLDOWN_DAYS=5)
    state, tr = pos.update(state, [_hit("X.BK")], _fr(10.0), "2026-07-04")
    assert "X.BK" not in state
    assert tr["skipped"] == ["X.BK"]
    assert not tr["holding"]


def test_reentry_allowed_after_cooldown_elapses():
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    state, _ = pos.update(state, [], _fr(8.9), "2026-07-02")          # STOP flagged
    state, _ = pos.update(state, [], _fr(8.9), "2026-07-03")          # dropped @ 07-03
    # 5+ calendar days later -> cooldown cleared, a fresh signal re-enters normally
    state, tr = pos.update(state, [_hit("X.BK")], _fr(10.0), "2026-07-09")
    assert state["X.BK"]["state"] == "HOLDING"
    assert [r["ticker"] for r in tr["holding"]] == ["X.BK"]
    assert not tr["skipped"]


def test_cooldown_ledger_purges_and_hidden_from_holding_view():
    """The reserved bookkeeping key must never leak into holding_view()'s output."""
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    state, _ = pos.update(state, [], _fr(8.9), "2026-07-02")
    state, _ = pos.update(state, [], _fr(8.9), "2026-07-03")          # dropped, cooldown set
    assert pos._COOLDOWN_KEY in state
    holding, t1, sell = pos.holding_view(state)
    assert not holding and not t1 and not sell
    # advance well past COOLDOWN_DAYS with no re-fire -> the ledger entry purges itself
    state, _ = pos.update(state, [], _fr(8.9), "2026-07-20")
    assert pos._COOLDOWN_KEY not in state


# ---- position cap (composite) -------------------------------------------------------------

def _many(tickers, px=10.0):
    return {t: _df(px) for t in tickers}


def test_cap_rotates_weakest_existing():
    """With 3 held and cap 2, the lowest-composite EXISTING name rotates out (ROTATE)."""
    hits = [_hit("A.BK"), _hit("B.BK"), _hit("C.BK")]
    frames = _many(["A.BK", "B.BK", "C.BK"])
    ranks = {"A.BK": 3.0, "B.BK": 2.0, "C.BK": 1.0}
    # seed all three (day 1, no cap so they enter), then apply cap on day 2
    state, _ = pos.update({}, hits, frames, "2026-07-01")
    state, tr = pos.update(state, [], frames, "2026-07-02", ranks=ranks, max_positions=2)
    assert {r["ticker"] for r in tr["holding"]} == {"A.BK", "B.BK"}
    assert [r["ticker"] for r in tr["sell_today"]] == ["C.BK"]
    assert state["C.BK"]["sell_reason"] == "ROTATE"


def test_cap_skips_weak_new_entry():
    """Book full of stronger names -> a weak fresh hit is silently skipped, not opened."""
    frames = _many(["A.BK", "B.BK", "D.BK"])
    ranks = {"A.BK": 3.0, "B.BK": 2.0, "D.BK": 0.5}
    state, _ = pos.update({}, [_hit("A.BK"), _hit("B.BK")], frames, "2026-07-01",
                          ranks=ranks, max_positions=2)
    state, tr = pos.update(state, [_hit("D.BK")], frames, "2026-07-02",
                           ranks=ranks, max_positions=2)
    assert "D.BK" not in state
    assert tr["skipped"] == ["D.BK"]
    assert {r["ticker"] for r in tr["holding"]} == {"A.BK", "B.BK"}


def test_cap_off_when_no_ranks():
    frames = _many(["A.BK", "B.BK", "C.BK"])
    state, _ = pos.update({}, [_hit("A.BK"), _hit("B.BK"), _hit("C.BK")], frames, "2026-07-01")
    state, tr = pos.update(state, [], frames, "2026-07-02", ranks=None, max_positions=2)
    assert len(tr["holding"]) == 3                     # uncapped without a ranking


def test_holding_view_splits_states_and_events():
    state = {
        "A.BK": {"state": "HOLDING", "phase": "FULL", "entry_close": 10, "cur": 11,
                 "pl_pct": 10, "status": "HOLD"},
        "B.BK": {"state": "HOLDING", "phase": "RUN", "entry_close": 9, "cur": 9.9,
                 "pl_pct": 10, "status": "RUN", "t1_date": "2026-07-02"},
        "C.BK": {"state": "SELL_FLAGGED", "entry_close": 8, "cur": 8.2, "pl_pct": 2.5,
                 "status": "TRAIL", "sell_reason": "TRAIL", "flagged_date": "2026-07-02"},
    }
    holding, t1, sell = pos.holding_view(state, asof="2026-07-02")
    assert {r["ticker"] for r in holding} == {"A.BK", "B.BK"}
    assert [r["ticker"] for r in t1] == ["B.BK"]
    assert [r["ticker"] for r in sell] == ["C.BK"]


def test_notes():
    assert "EMA20" in pos.sell_note("TRAIL")
    assert "สต็อป" in pos.sell_note("STOP")
    assert "เสมอตัว" in pos.sell_note("BE")
    assert "สับเปลี่ยน" in pos.sell_note("ROTATE")
    assert "T1" in pos.t1_note()


def test_save_load_roundtrip(tmp_path):
    p = str(tmp_path / "positions.json")
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    pos.save(state, p)
    assert pos.load(p)["X.BK"]["phase"] == "FULL"


def test_load_missing_file_returns_empty(tmp_path):
    assert pos.load(str(tmp_path / "nope.json")) == {}
