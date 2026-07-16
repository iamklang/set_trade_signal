#!/usr/bin/env python3
"""
bt_portfolio.py — PORTFOLIO-level backtest of the shipped managed watchlist to size the
position cap. Unlike bt_exits.py (independent trades), this runs ONE equal-weight book with
a hard concurrent-position cap and composite rotation — exactly positions.py's live rule —
and marks to market daily, so it answers "which cap N maximises risk-adjusted profit".

Model (close-based, matching the EOD live system):
  • Universe SET100, Yahoo daily. Each date, in order: run exits, then fill/rotate entries.
  • Entry: a BUY(dip) name not already held. Fill an open slot; if full, ROTATE only when the
    candidate's composite (mom+trend, monthly) beats the weakest holding; else skip.
  • Exit (V5 let-run): close<=stop -> STOP (pre-T1) / BE (post-T1); close>=T1 -> stop=breakeven,
    RUN; (RUN) close<EMA20 -> TRAIL. No T2 cap.
  • Sizing: equal-weight, each new position = equity/N of current equity; idle slots = cash.
  • Cost 0.30%/side folded into fills. Metrics from the daily equity curve + closed trades.

Usage: python bt_portfolio.py [--years 10] [--caps 5,8,10,12,15,20,30]
NOT advice — mechanics only; SET100 = today's survivors (survivorship-inflated).
"""
import argparse
import bisect
import sys

import numpy as np
import pandas as pd

HERE = "/Users/klang/Git/trading_dr"
sys.path.insert(0, HERE)
import setdw_signal as sig       # noqa: E402
import composite                 # noqa: E402
import set_data                  # noqa: E402
import costs                     # noqa: E402

COST = 0.003
COOLDOWN = 5


def load_universe(path):
    with open(path) as f:
        return [t.split("#")[0].strip() for t in f if t.split("#")[0].strip()]


import bullish_signals as bull      # noqa: E402


def build(frames, entry="dip"):
    """Align every name onto one date index -> CLOSE/EMA/BUY/LL matrices (dates x tickers).
    `entry` picks the ENTRY signal: dip (strict BUY), breakout, reclaim, or any (dip|brk|rcl)."""
    cfg = {"rsi_min": sig.RSI_MIN, "adx_min": sig.ADX_MIN, "need_vol_conf": True}
    close, ema, buy, ll, turn = {}, {}, {}, {}, {}
    for t, df in frames.items():
        d = bull.add_signals(df, cfg)          # dip/breakout/reclaim/trend + ema + llStop
        close[t] = d["Close"]; ema[t] = d["ema"]; ll[t] = d["llStop"]
        turn[t] = (d["Close"] * d["Volume"]).rolling(20).median()   # trailing daily turnover (THB)
        if entry == "any":
            buy[t] = d[["dip", "breakout", "reclaim"]].any(axis=1)
        elif entry == "dipbrk":            # dip AND breakout — momentum-confirmed dip (the 38%)
            buy[t] = d["dip"] & d["breakout"]
        elif entry == "dip_or_brk":        # dip OR breakout — robust dip + momentum leg
            buy[t] = d["dip"] | d["breakout"]
        else:
            buy[t] = d[entry]
    CLOSE = pd.DataFrame(close).sort_index()
    return (CLOSE, pd.DataFrame(ema).reindex(CLOSE.index),
            pd.DataFrame(buy).reindex(CLOSE.index).fillna(False),
            pd.DataFrame(ll).reindex(CLOSE.index),
            pd.DataFrame(turn).reindex(CLOSE.index))


def monthly_scores(frames, dates):
    """({month_end: {ticker: composite_score}}, {month_end: {ticker: quintile}}) for the
    mom+trend cap ranking AND the composite-tilt position sizing."""
    me = pd.Series(index=dates, data=0).resample("ME").last().index
    sc, qu = {}, {}
    for d in me:
        R = composite.cross_section_scores(frames, asof=d,
                                           weights={"mom": 1, "trend": 1, "lowvol": 0})
        sc[d] = {} if R.empty else {t: float(R.loc[t, "composite"]) for t in R.index}
        qu[d] = {} if R.empty else {t: int(R.loc[t, "quintile"]) for t in R.index}
    return sorted(sc), sc, qu         # (sorted month_ends, score map, quintile map)


TARGET_VOL = 0.18                     # annualised, for the vol-target overlay
DD_BRAKE = 0.12                       # portfolio drawdown that halves new sizing


def run(cap, dates, CLOSE, EMA, BUY, LL, month_ends, mscores, mquint, weight_fn=None,
        overlay=None, mvol=None, idx=None, idxsma=None, cost_fn=None,
        turn=None, min_turnover=0.0, liq_cost=False, vola=None):
    """One portfolio, `cap` concurrent positions. weight_fn(score, quintile)->size multiplier
    (default 1.0 = equal-weight equity/N). `overlay` scales TOTAL new exposure by a regime
    factor: 'voltgt' (target 18% vol via trailing market vol `mvol`), 'ddbrake' (halve sizing
    when the portfolio is >12% off its peak), 'regime' (halve when the index `idx` is below its
    200-SMA `idxsma`), or 'combo' (voltgt×ddbrake). Returns (equity, trades, rotations, avg_open)."""
    weight_fn = weight_fn or (lambda s, q, v: 1.0)   # equal-weight; sig matches mult()'s 3-arg call
    cost_fn = cost_fn or (lambda px: COST)      # per-SIDE cost as a fraction of the fill price
    cash = 1.0
    peak = 1.0
    pos = {}                          # ticker -> {shares, entry, stop, t1, phase, amt}
    last_exit = {}                    # ticker -> date index of last close (cooldown)
    eq_curve, trades, rotations, open_counts = [], [], 0, []
    turn_row = None                   # this date's trailing turnover row (set each iteration)

    def scost(t, px):
        # Per-name cost from liquidity (thin -> wider spread -> costlier) when liq_cost is on;
        # otherwise the flat/constant cost_fn. Uses the current date's turnover row.
        if liq_cost and turn_row is not None:
            return costs.side_cost(px, spread_ticks=costs.spread_ticks_for(turn_row.get(t)))
        return cost_fn(px)

    def ovl_factor(di, cur_dd):
        f = 1.0
        if overlay in ("voltgt", "combo") and mvol is not None:
            v = mvol[di]
            if v and not np.isnan(v) and v > 0:
                f *= min(1.0, max(0.3, TARGET_VOL / v))
        if overlay in ("ddbrake", "combo"):
            if cur_dd <= -DD_BRAKE:
                f *= 0.5
        if overlay == "regime" and idx is not None and idxsma is not None:
            s = idxsma[di]
            if s and not np.isnan(s) and idx[di] < s:
                f *= 0.5
        return f

    def score(di, t):
        i = bisect.bisect_right(month_ends, dates[di]) - 1
        return mscores[month_ends[i]].get(t, float("-inf")) if i >= 0 else float("-inf")

    def quint(di, t):
        i = bisect.bisect_right(month_ends, dates[di]) - 1
        return mquint[month_ends[i]].get(t, 3) if i >= 0 else 3

    def mult(di, t):
        s = score(di, t)
        v = vola.iloc[di].get(t) if vola is not None else None
        return weight_fn(s if s != float("-inf") else 0.0, quint(di, t), v)

    def close_pos(t, px):
        nonlocal cash
        got = pos[t]["shares"] * px * (1 - scost(t, px))
        trades.append(got / pos[t]["amt"] - 1)
        cash += got
        last_exit[t] = di
        del pos[t]

    for di, d in enumerate(dates):
        cl = CLOSE.iloc[di]; em = EMA.iloc[di]
        turn_row = turn.iloc[di] if turn is not None else None   # today's per-name turnover

        # 1) exits (close-based, V5)
        for t in list(pos):
            px = cl.get(t)
            if px is None or np.isnan(px):
                continue
            p = pos[t]
            if px <= p["stop"]:
                close_pos(t, px)
            elif p["phase"] == "FULL" and px >= p["t1"]:
                p["phase"] = "RUN"; p["stop"] = p["entry"]      # breakeven, let it run
            elif p["phase"] == "RUN":
                e = em.get(t)
                if e is not None and not np.isnan(e) and px < e:
                    close_pos(t, px)

        # 2) entries — BUY(dip) names not held, off cooldown, ranked by composite desc
        eq_now = cash + sum(pos[t]["shares"] * cl.get(t)
                            for t in pos if cl.get(t) and not np.isnan(cl.get(t)))
        peak = max(peak, eq_now)
        ovl = ovl_factor(di, eq_now / peak - 1.0)     # regime exposure scaler for new entries
        bt = BUY.iloc[di]
        cands = [t for t in BUY.columns
                 if bool(bt.get(t)) and t not in pos
                 and (di - last_exit.get(t, -10_000)) >= COOLDOWN
                 and cl.get(t) and not np.isnan(cl.get(t)) and LL.iloc[di].get(t)
                 and cl.get(t) > LL.iloc[di].get(t) > 0
                 and (min_turnover <= 0 or turn_row is None
                      or (turn_row.get(t) or 0) >= min_turnover)]   # liquidity gate
        for t in sorted(cands, key=lambda t: score(di, t), reverse=True):
            amt = min(eq_now / cap * mult(di, t) * ovl, cash)
            if amt <= 1e-9:
                break
            if len(pos) >= cap:
                weakest = min(pos, key=lambda h: score(di, h))
                if score(di, t) <= score(di, weakest):
                    break                                       # sorted desc -> none qualify
                wpx = cl.get(weakest)
                if wpx is None or np.isnan(wpx):
                    continue
                close_pos(weakest, wpx); rotations += 1
                amt = min(eq_now / cap * mult(di, t) * ovl, cash)
            entry = cl.get(t); stop = LL.iloc[di].get(t)
            pos[t] = {"shares": amt * (1 - scost(t, entry)) / entry, "entry": entry, "stop": stop,
                      "t1": entry + (entry - stop), "phase": "FULL", "amt": amt}
            cash -= amt

        eq = cash + sum(pos[t]["shares"] * cl.get(t)
                        for t in pos if cl.get(t) and not np.isnan(cl.get(t)))
        eq_curve.append(eq); open_counts.append(len(pos))

    return (pd.Series(eq_curve, index=dates), trades, rotations,
            float(np.mean(open_counts)))


def metrics(eq, trades):
    r = eq.pct_change().dropna()
    yrs = len(eq) / 252
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if eq.iloc[-1] > 0 else -1
    sharpe = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    tr = np.array(trades)
    wins, losses = tr[tr > 0].sum(), -tr[tr < 0].sum()
    pf = wins / losses if losses > 0 else np.inf
    hit = (tr > 0).mean() * 100 if len(tr) else np.nan
    return cagr, sharpe, dd, pf, hit, len(tr)


def _clip(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


VOL_REF = 0.02          # reference daily vol (~2%) to centre the inverse-vol (Kelly) tilt at ~1


def _invvol(v):
    """Inverse-vol (risk-parity) multiplier centred at VOL_REF: half-size a 2×-vol name, double
    a half-vol one. The 1/σ term Kelly puts in the denominator — 'vol belongs in SIZING'."""
    if v is None or v != v or v <= 0:
        return 1.0
    return _clip(VOL_REF / v, 0.4, 2.0)


_QUINT = {1: 1.5, 2: 1.25, 3: 1.0, 4: 0.75, 5: 0.5}

# Sizing schemes: weight_fn(composite_score, quintile, daily_vol) -> size multiplier (avg ~1 so
# total deployment ≈ equal-weight; the tilt only redistributes across held names). The Kelly
# variants add the inverse-vol (1/σ) term on top of the composite-edge tilt = fractional Kelly.
SIZINGS = {
    "equal":     lambda s, q, v: 1.0,
    "comp0.6":   lambda s, q, v: _clip(1 + 0.6 * s, 0.5, 2.0),
    "quintile":  lambda s, q, v: _QUINT.get(q, 1.0),
    "invvol":    lambda s, q, v: _invvol(v),                        # risk-parity, no edge tilt
    "kelly_q":   lambda s, q, v: _QUINT.get(q, 1.0) * _invvol(v),   # quintile edge × inverse-vol
    "kelly_lin": lambda s, q, v: _clip(1 + 0.6 * s, 0.5, 2.0) * _invvol(v),  # linear edge × 1/σ
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--universe", default=f"{HERE}/set100.bk.txt")
    ap.add_argument("--cap", type=int, default=12, help="fixed position cap for the sizing sweep")
    ap.add_argument("--caps", default=None, help="if set, sweep these caps EQUAL-weight instead")
    ap.add_argument("--entry", default="dip",
                    choices=["dip", "breakout", "reclaim", "any", "dipbrk", "dip_or_brk"],
                    help="entry signal (default dip = the live watchlist; 'any'=dip|brk|rcl; "
                         "dipbrk=dip&breakout momentum-confirmed; dip_or_brk=dip|breakout)")
    ap.add_argument("--overlay", default="none",
                    choices=["none", "voltgt", "ddbrake", "regime", "combo", "sweep"],
                    help="regime exposure overlay on new sizing; 'sweep' compares all at "
                         "quintile sizing / --cap")
    ap.add_argument("--cost-model", default="flat", choices=["flat", "tick", "tickliq"],
                    help="flat = 0.3%%/side (legacy); tick = SET tick half-spread at a constant "
                         "--spread-ticks; tickliq = per-name spread inferred from each name's "
                         "trailing turnover (thin names cost more)")
    ap.add_argument("--spread-ticks", type=float, default=1.0,
                    help="with --cost-model tick: quoted spread in ticks (1=liquid taker, "
                         "0=perfect limit fills, >1=thin names)")
    ap.add_argument("--min-turnover", type=float, default=0.0,
                    help="liquidity gate: skip entries whose trailing daily turnover (THB) is "
                         "below this (e.g. 20e6 = ฿20M/day). 0=off. Thin names' 2-tick spreads "
                         "kill the edge (bt cost experiment).")
    a = ap.parse_args()
    cost_fn = (None if a.cost_model != "tick"
               else (lambda px: costs.side_cost(px, spread_ticks=a.spread_ticks)))
    liq_cost = (a.cost_model == "tickliq")

    tickers = load_universe(a.universe)
    print(f"fetching {len(tickers)} names, {a.years}y | entry={a.entry} ...")
    raw = set_data.fetch_yahoo_all(tickers, period=f"{a.years}y")
    frames = {t: df for t, df in raw.items()
              if df is not None and len(df) >= sig.SMA_LEN + 60}
    print(f"usable: {len(frames)} names; building matrices + monthly composite ...")
    CLOSE, EMA, BUY, LL, TURN = build(frames, entry=a.entry)
    dates = list(CLOSE.index)
    month_ends, mscores, mquint = monthly_scores(frames, CLOSE.index)
    print(f"  {dates[0].date()}..{dates[-1].date()} ({len(dates)} bars)\n")

    VOLA = CLOSE.pct_change().rolling(60).std()     # per-name daily vol for the Kelly (1/σ) tilt
    # Market proxy (equal-weight universe) for the vol-target + regime overlays.
    mkt_ret = CLOSE.pct_change().mean(axis=1)
    mvol = (mkt_ret.rolling(20).std() * np.sqrt(252)).values
    idxs = (1 + mkt_ret.fillna(0)).cumprod()
    idx, idxsma = idxs.values, idxs.rolling(200).mean().values
    QT = SIZINGS["quintile"]

    if a.overlay == "sweep":            # compare exposure overlays at quintile sizing
        print(f"Overlay sweep @ cap {a.cap}, quintile sizing, entry={a.entry}:\n")
        hdr = (f"{'overlay':>10}{'CAGR':>9}{'Sharpe':>8}{'maxDD':>9}{'PF':>6}{'hit%':>7}"
               f"{'trades':>8}{'avgOpen':>9}{'finalEq':>9}")
        print(hdr); print("-" * len(hdr))
        for ov in ["none", "voltgt", "ddbrake", "regime", "combo"]:
            eq, tr, rots, ao = run(a.cap, dates, CLOSE, EMA, BUY, LL, month_ends, mscores,
                                   mquint, weight_fn=QT, overlay=(None if ov == "none" else ov),
                                   mvol=mvol, idx=idx, idxsma=idxsma, cost_fn=cost_fn, vola=VOLA)
            cagr, sharpe, dd, pf, hit, n = metrics(eq, tr)
            print(f"{ov:>10}{cagr*100:>8.1f}%{sharpe:>8.2f}{dd*100:>8.1f}%{pf:>6.2f}"
                  f"{hit:>7.1f}{n:>8}{ao:>9.1f}{eq.iloc[-1]:>9.2f}")
        print("-" * len(hdr))
        print("  an overlay earns its keep only if it CUTS maxDD while holding/raising Sharpe "
              "on BOTH windows — else it's just de-risking away return.")
        return

    ov = None if a.overlay == "none" else a.overlay

    if a.caps:                          # cap sweep (equal-weight) — the earlier mode
        hdr = (f"{'cap':>5}{'CAGR':>9}{'Sharpe':>8}{'maxDD':>9}{'PF':>6}{'hit%':>7}"
               f"{'trades':>8}{'rot':>6}{'avgOpen':>9}{'finalEq':>9}")
        print(hdr); print("-" * len(hdr))
        for cap in [int(x) for x in a.caps.split(",")]:
            eq, trades, rots, avg_open = run(cap, dates, CLOSE, EMA, BUY, LL,
                                             month_ends, mscores, mquint,
                                             overlay=ov, mvol=mvol, idx=idx, idxsma=idxsma,
                                             cost_fn=cost_fn, turn=TURN,
                                             min_turnover=a.min_turnover, liq_cost=liq_cost)
            cagr, sharpe, dd, pf, hit, n = metrics(eq, trades)
            print(f"{cap:>5}{cagr*100:>8.1f}%{sharpe:>8.2f}{dd*100:>8.1f}%{pf:>6.2f}"
                  f"{hit:>7.1f}{n:>8}{rots:>6}{avg_open:>9.1f}{eq.iloc[-1]:>9.2f}")
        return

    # Sizing-scheme sweep at a fixed cap.
    print(f"Position-sizing sweep @ cap {a.cap} (composite tilt vs equal-weight):\n")
    hdr = (f"{'sizing':>10}{'CAGR':>9}{'Sharpe':>8}{'maxDD':>9}{'PF':>6}{'hit%':>7}"
           f"{'trades':>8}{'avgOpen':>9}{'finalEq':>9}")
    print(hdr); print("-" * len(hdr))
    rows = []
    for name, wf in SIZINGS.items():
        eq, trades, rots, avg_open = run(a.cap, dates, CLOSE, EMA, BUY, LL,
                                         month_ends, mscores, mquint, weight_fn=wf,
                                         overlay=ov, mvol=mvol, idx=idx, idxsma=idxsma,
                                         cost_fn=cost_fn, turn=TURN,
                                         min_turnover=a.min_turnover, liq_cost=liq_cost, vola=VOLA)
        cagr, sharpe, dd, pf, hit, n = metrics(eq, trades)
        rows.append((name, cagr, sharpe, dd))
        print(f"{name:>10}{cagr*100:>8.1f}%{sharpe:>8.2f}{dd*100:>8.1f}%{pf:>6.2f}"
              f"{hit:>7.1f}{n:>8}{avg_open:>9.1f}{eq.iloc[-1]:>9.2f}")
    print("-" * len(hdr))
    base = next(r for r in rows if r[0] == "equal")
    bestS = max(rows, key=lambda x: x[2]); bestC = max(rows, key=lambda x: x[1])
    print(f"\n  equal-weight baseline: CAGR {base[1]*100:.1f}%  Sharpe {base[2]:.2f}")
    print(f"  best Sharpe: {bestS[0]} ({bestS[2]:.2f})   best CAGR: {bestC[0]} ({bestC[1]*100:.1f}%)")
    print("  composite tilt helps only if it beats 'equal' on BOTH windows — otherwise the score "
          "predicts selection (Q1 entry) better than sizing.")


if __name__ == "__main__":
    main()
