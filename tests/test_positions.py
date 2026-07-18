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


def test_zero_size_hit_not_recorded():
    """A hit the capital guard trimmed to 0 shares must not become a phantom holding
    (it would occupy a slot in the ~12-name cap). It's skipped and can re-fire later."""
    zero = ("X.BK", {"close": 10.0, "stop": 9.0, "t1": 11.0, "t2": 11.5,
                     "rsi": 60, "adx": 25, "size": 0, "distPct": -0.5})
    state, tr = pos.update({}, [zero], _fr(10.0), "2026-07-01")
    assert "X.BK" not in state          # no phantom position written
    assert "X.BK" in tr["skipped"]
    assert not tr["holding"]


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
    state, _ = pos.update(state, [], _fr(8.9), "2026-07-03")          # dropped @ 07-03 (Fri)
    # 5 XBKK trading sessions later (Mon 06 … Fri 10) -> cooldown cleared, re-enters normally
    state, tr = pos.update(state, [_hit("X.BK")], _fr(10.0), "2026-07-10")
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
    """With 3 held and cap 2, the lowest-composite EXISTING name rotates out (ROTATE)
    once it has been held past MIN_HOLD_BARS and is not in profit."""
    hits = [_hit("A.BK"), _hit("B.BK"), _hit("C.BK")]
    frames = _many(["A.BK", "B.BK", "C.BK"])
    ranks = {"A.BK": 3.0, "B.BK": 2.0, "C.BK": 1.0}
    state, _ = pos.update({}, hits, frames, "2026-07-01")
    # advance past MIN_HOLD_BARS (5) so the guard doesn't block
    state, tr = pos.update(state, [], frames, "2026-07-14", ranks=ranks, max_positions=2)
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


# ---- XD/split re-anchor (_rescale_levels) --------------------------------------------

def _df_seq(closes, start="2026-06-01"):
    idx = pd.date_range(start, periods=len(closes), freq="D")
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes,
                         "Close": closes, "Volume": [1_000_000] * len(closes)}, index=idx)


def test_xd_adjustment_does_not_false_stop():
    """A 3% dividend adjustment rescales Yahoo history; the stored stop must rescale too,
    so a close above the ADJUSTED stop (but below the stale one) stays HOLDING."""
    f1 = {"X.BK": _df_seq([10.0] * 30)}                      # last bar 2026-06-30
    state, _ = pos.update({}, [_hit("X.BK")], f1, "2026-06-30")
    assert state["X.BK"]["stop"] == 9.0
    # XD: Yahoo scales all prior bars x0.97; new bar closes 8.9 (above 9.0*0.97=8.73)
    f2 = {"X.BK": _df_seq([10.0 * 0.97] * 30 + [8.9])}
    state, tr = pos.update(state, [], f2, "2026-07-01")
    assert state["X.BK"]["state"] == "HOLDING"
    assert not tr["sell_today"]
    assert state["X.BK"]["entry_close"] == 9.7
    assert state["X.BK"]["stop"] == 8.73
    assert state["X.BK"]["t1"] == 10.67                      # 11.0 x 0.97
    # idempotent: same scale next run -> no further drift
    f3 = {"X.BK": _df_seq([10.0 * 0.97] * 30 + [8.9, 8.9])}
    state, _ = pos.update(state, [], f3, "2026-07-02")
    assert state["X.BK"]["stop"] == 8.73


def test_xd_adjustment_run_phase_keeps_breakeven_equal_entry():
    """After T1 the stop sits at entry (breakeven); rescaling must keep stop == entry."""
    f1 = {"X.BK": _df_seq([10.0] * 30)}
    state, _ = pos.update({}, [_hit("X.BK")], f1, "2026-06-30")
    state, _ = pos.update(state, [], {"X.BK": _df_seq([10.0] * 30 + [11.0])}, "2026-07-01")
    assert state["X.BK"]["phase"] == "RUN" and state["X.BK"]["stop"] == 10.0
    f2 = {"X.BK": _df_seq([10.0 * 0.95] * 31 + [10.2])}      # 5% dividend, still above BE
    state, tr = pos.update(state, [], f2, "2026-07-02")
    assert state["X.BK"]["state"] == "HOLDING"
    assert state["X.BK"]["stop"] == state["X.BK"]["entry_close"] == 9.5


def test_small_drift_below_tolerance_untouched():
    """Sub-tolerance drift (rounding noise) must not rescale anything."""
    f1 = {"X.BK": _df_seq([10.0] * 30)}
    state, _ = pos.update({}, [_hit("X.BK")], f1, "2026-06-30")
    f2 = {"X.BK": _df_seq([10.001] * 30 + [9.8])}            # 0.01% << ADJ_TOL
    state, _ = pos.update(state, [], f2, "2026-07-01")
    assert state["X.BK"]["stop"] == 9.0 and state["X.BK"]["entry_close"] == 10.0


# ---- committed / available capital -------------------------------------------------------

def test_committed_capital_empty():
    assert pos.committed_capital({}) == 0

def test_committed_capital_with_holdings():
    state = {
        "A.BK": {"state": "HOLDING", "entry_close": 10.0, "size": 100},
        "B.BK": {"state": "HOLDING", "entry_close": 20.0, "size": 50},
    }
    assert pos.committed_capital(state) == 2000.0  # 10*100 + 20*50

def test_committed_capital_ignores_sell_flagged():
    state = {
        "A.BK": {"state": "HOLDING", "entry_close": 10.0, "size": 100},
        "B.BK": {"state": "SELL_FLAGGED", "entry_close": 20.0, "size": 50},
    }
    assert pos.committed_capital(state) == 1000.0

def test_committed_capital_ignores_cooldown():
    state = {
        "A.BK": {"state": "HOLDING", "entry_close": 10.0, "size": 100},
        pos._COOLDOWN_KEY: {"X.BK": "2026-07-01"},
    }
    assert pos.committed_capital(state) == 1000.0

def test_available_capital():
    state = {"A.BK": {"state": "HOLDING", "entry_close": 10.0, "size": 100}}
    assert pos.available_capital(state, 5000) == 4000.0

def test_available_capital_floored_at_zero():
    state = {"A.BK": {"state": "HOLDING", "entry_close": 100.0, "size": 100}}
    assert pos.available_capital(state, 5000) == 0  # committed 10000 > equity 5000


# ---- opportunity score -------------------------------------------------------------------

def test_opportunity_score_full_phase():
    rec = {"phase": "FULL", "cur": 10.0, "t1": 12.0}
    assert abs(pos.opportunity_score(rec) - 0.2) < 1e-6  # (12-10)/10

def test_opportunity_score_near_t1():
    rec = {"phase": "FULL", "cur": 11.9, "t1": 12.0}
    assert pos.opportunity_score(rec) < 0.01  # very little upside left

def test_opportunity_score_past_t1_run_phase_with_ema():
    rec = {"phase": "RUN", "cur": 13.0, "t1": 12.0, "ema20": 12.5}
    score = pos.opportunity_score(rec)
    assert 0 < score < 0.05  # trail cushion (13-12.5)/13

def test_opportunity_score_run_phase_no_ema():
    rec = {"phase": "RUN", "cur": 13.0, "t1": 12.0}
    assert pos.opportunity_score(rec) == 0.01  # fallback

def test_opportunity_score_missing_data():
    assert pos.opportunity_score({}) == 0.0
    assert pos.opportunity_score({"cur": 10.0}) == 0.0


# ---- proactive rotation ------------------------------------------------------------------

def test_proactive_rotation_swaps_when_better_opportunity():
    """New entry with clearly better upside displaces the weakest incumbent
    (incumbent must be past MIN_HOLD_BARS and not in profit)."""
    # Seed 2 holdings, both near their T1 (low opportunity)
    state, _ = pos.update({}, [_hit("A.BK", close=10.9, stop=9.0, t1=11.0),
                               _hit("B.BK", close=10.8, stop=9.0, t1=11.0)],
                          _many(["A.BK", "B.BK"]), "2026-07-01",
                          ranks={"A.BK": 2.0, "B.BK": 1.0}, max_positions=2)
    # Advance past MIN_HOLD_BARS; new entry with fresh upside
    frames = {**_many(["A.BK", "B.BK"]), "C.BK": _df(10.0)}
    state, tr = pos.update(state, [_hit("C.BK", close=10.0, stop=9.0, t1=11.0)],
                           frames, "2026-07-14",
                           ranks={"A.BK": 2.0, "B.BK": 1.0, "C.BK": 1.5},
                           max_positions=2)
    rotated = [r["ticker"] for r in tr["sell_today"] if r.get("sell_reason") == "ROTATE"]
    assert len(rotated) == 1
    assert "C.BK" in state and state["C.BK"]["state"] == "HOLDING"

def test_proactive_rotation_threshold_prevents_churn():
    """Marginal improvement (< 5%) does NOT trigger proactive rotation."""
    # 2 holdings near their T1 (low opp) — both have ~5% upside, similar opp
    state, _ = pos.update({}, [_hit("A.BK", close=10.5, stop=9.0, t1=11.0),
                               _hit("B.BK", close=10.5, stop=9.0, t1=11.0)],
                          _many(["A.BK", "B.BK"]), "2026-07-01",
                          ranks={"A.BK": 2.0, "B.BK": 2.0}, max_positions=3)
    # New entry has marginally better opp (~6% vs ~5% = diff < 5% threshold)
    frames = {**_many(["A.BK", "B.BK"]), "C.BK": _df(10.0)}
    state, tr = pos.update(state, [_hit("C.BK", close=10.0, stop=9.0, t1=10.6)],
                           frames, "2026-07-02",
                           ranks={"A.BK": 2.0, "B.BK": 2.0, "C.BK": 2.0},
                           max_positions=3)
    rotated = [r for r in tr["sell_today"] if r.get("sell_reason") == "ROTATE"]
    assert len(rotated) == 0

def test_no_rotation_when_slots_available():
    """No rotation when book is under max_positions — new entry just fills a slot."""
    state, _ = pos.update({}, [_hit("A.BK")], _many(["A.BK"]), "2026-07-01",
                          ranks={"A.BK": 2.0}, max_positions=3)
    frames = {**_many(["A.BK"]), "B.BK": _df(10.0)}
    state, tr = pos.update(state, [_hit("B.BK")], frames, "2026-07-02",
                           ranks={"A.BK": 2.0, "B.BK": 1.0}, max_positions=3)
    assert not any(r.get("sell_reason") == "ROTATE" for r in tr["sell_today"])
    assert "B.BK" in state and state["B.BK"]["state"] == "HOLDING"


# ---- eff_stop / ema20 / opp_score stored in update() ------------------------------------

def test_eff_stop_full_phase():
    state, tr = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    assert state["X.BK"]["eff_stop"] == 9.0  # structural stop

def test_eff_stop_run_phase_uses_ema():
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    state, _ = pos.update(state, [], _fr(11.0), "2026-07-02")  # hits T1 -> RUN
    assert state["X.BK"]["phase"] == "RUN"
    # Next bar (already RUN): eff_stop = max(stop=10, ema). With 30 flat bars ema≈close≈11
    state, _ = pos.update(state, [], _fr(11.0), "2026-07-03")
    assert state["X.BK"]["eff_stop"] >= 10.0

def test_opp_score_stored():
    state, _ = pos.update({}, [_hit("X.BK")], _fr(10.0), "2026-07-01")
    assert state["X.BK"]["opp_score"] is not None
    assert state["X.BK"]["opp_score"] > 0


# ---- rotation guards: protect winners + min hold time ---------------------------

def test_winner_protected_from_cap_rotation():
    """A position in profit must not be rotated out even if it has the lowest composite."""
    hits = [_hit("A.BK", close=10.0), _hit("B.BK", close=10.0), _hit("C.BK", close=10.0)]
    frames = _many(["A.BK", "B.BK", "C.BK"])
    ranks = {"A.BK": 3.0, "B.BK": 2.0, "C.BK": 1.0}
    state, _ = pos.update({}, hits, frames, "2026-07-01")
    # C is weakest by rank but is now in profit (cur 11 > entry 10)
    frames_up = {t: _df(11.0) for t in ["A.BK", "B.BK", "C.BK"]}
    # advance well past MIN_HOLD_BARS so only the profit guard is tested
    state, tr = pos.update(state, [], frames_up, "2026-07-14", ranks=ranks, max_positions=2)
    # C is in profit -> protected, should NOT be rotated even though over cap
    assert state["C.BK"]["state"] == pos.HOLDING
    assert not any(r["ticker"] == "C.BK" and r.get("sell_reason") == "ROTATE"
                   for r in tr["sell_today"])


def test_young_position_protected_from_cap_rotation():
    """A position held less than MIN_HOLD_BARS must not be rotated out."""
    hits = [_hit("A.BK"), _hit("B.BK"), _hit("C.BK")]
    frames = _many(["A.BK", "B.BK", "C.BK"])
    ranks = {"A.BK": 3.0, "B.BK": 2.0, "C.BK": 1.0}
    state, _ = pos.update({}, hits, frames, "2026-07-01")
    # Next day (1 bar held < MIN_HOLD_BARS=5), even though C is weakest
    state, tr = pos.update(state, [], frames, "2026-07-02", ranks=ranks, max_positions=2)
    assert state["C.BK"]["state"] == pos.HOLDING
    assert not any(r["ticker"] == "C.BK" and r.get("sell_reason") == "ROTATE"
                   for r in tr["sell_today"])


def test_loser_past_min_hold_can_be_rotated():
    """A losing position held long enough is still eligible for rotation."""
    hits = [_hit("A.BK", close=10.0), _hit("B.BK", close=10.0), _hit("C.BK", close=10.0)]
    frames = _many(["A.BK", "B.BK", "C.BK"])
    ranks = {"A.BK": 3.0, "B.BK": 2.0, "C.BK": 1.0}
    state, _ = pos.update({}, hits, frames, "2026-07-01")
    # C is losing (cur 9.5 < entry 10) and held > MIN_HOLD_BARS
    frames_down = {t: _df(9.5) for t in ["A.BK", "B.BK", "C.BK"]}
    state, tr = pos.update(state, [], frames_down, "2026-07-14", ranks=ranks, max_positions=2)
    assert state["C.BK"]["sell_reason"] == "ROTATE"


def test_winner_protected_from_proactive_rotation():
    """A profitable incumbent must not be proactively rotated even with better new opportunity."""
    state, _ = pos.update({}, [_hit("A.BK", close=10.0, stop=9.0, t1=11.0),
                               _hit("B.BK", close=10.0, stop=9.0, t1=11.0)],
                          _many(["A.BK", "B.BK"]), "2026-07-01",
                          ranks={"A.BK": 2.0, "B.BK": 1.0}, max_positions=2)
    # B is now near T1 (low opp) but IN PROFIT — cur 10.9 > entry 10.0
    for t in state:
        if t == pos._COOLDOWN_KEY:
            continue
        state[t]["cur"] = 10.9
    # Advance past MIN_HOLD_BARS
    frames = {**_many(["A.BK", "B.BK"], px=10.9), "C.BK": _df(10.0)}
    state, tr = pos.update(state, [_hit("C.BK", close=10.0, stop=9.0, t1=12.0)],
                           frames, "2026-07-14",
                           ranks={"A.BK": 2.0, "B.BK": 1.0, "C.BK": 1.5},
                           max_positions=2)
    rotated = [r["ticker"] for r in tr["sell_today"] if r.get("sell_reason") == "ROTATE"]
    assert "B.BK" not in rotated


def test_young_position_protected_from_proactive_rotation():
    """An incumbent held < MIN_HOLD_BARS must not be proactively rotated."""
    state, _ = pos.update({}, [_hit("A.BK", close=10.9, stop=9.0, t1=11.0),
                               _hit("B.BK", close=10.9, stop=9.0, t1=11.0)],
                          _many(["A.BK", "B.BK"]), "2026-07-01",
                          ranks={"A.BK": 2.0, "B.BK": 1.0}, max_positions=2)
    # Day 2: B is young (1 bar) and losing — should still be protected by min hold
    frames = {**_many(["A.BK", "B.BK"]), "C.BK": _df(10.0)}
    state, tr = pos.update(state, [_hit("C.BK", close=10.0, stop=9.0, t1=12.0)],
                           frames, "2026-07-02",
                           ranks={"A.BK": 2.0, "B.BK": 1.0, "C.BK": 1.5},
                           max_positions=2)
    rotated = [r["ticker"] for r in tr["sell_today"] if r.get("sell_reason") == "ROTATE"]
    assert "B.BK" not in rotated


def test_missing_entry_date_protected_from_rotation():
    """A position without entry_date must not be rotated (treated as too young)."""
    hits = [_hit("A.BK"), _hit("B.BK"), _hit("C.BK")]
    frames = _many(["A.BK", "B.BK", "C.BK"])
    ranks = {"A.BK": 3.0, "B.BK": 2.0, "C.BK": 1.0}
    state, _ = pos.update({}, hits, frames, "2026-07-01")
    del state["C.BK"]["entry_date"]
    frames_down = {t: _df(9.5) for t in ["A.BK", "B.BK", "C.BK"]}
    state, tr = pos.update(state, [], frames_down, "2026-07-14", ranks=ranks, max_positions=2)
    assert state["C.BK"]["state"] == pos.HOLDING
    assert not any(r["ticker"] == "C.BK" and r.get("sell_reason") == "ROTATE"
                   for r in tr["sell_today"])


def test_over_cap_reported_when_all_protected():
    """When over-cap positions are all protected, trans['over_cap'] lists them."""
    hits = [_hit("A.BK", close=10.0), _hit("B.BK", close=10.0), _hit("C.BK", close=10.0)]
    frames = _many(["A.BK", "B.BK", "C.BK"])
    ranks = {"A.BK": 3.0, "B.BK": 2.0, "C.BK": 1.0}
    state, _ = pos.update({}, hits, frames, "2026-07-01")
    frames_up = {t: _df(11.0) for t in ["A.BK", "B.BK", "C.BK"]}
    state, tr = pos.update(state, [], frames_up, "2026-07-14", ranks=ranks, max_positions=2)
    assert len(tr["over_cap"]) >= 1
    assert all(t in state and state[t]["state"] == pos.HOLDING for t in tr["over_cap"])
