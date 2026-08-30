"""meta_label.py — Phase 1 of /quant-meta-label (López de Prado Pillar 4).

Builds the meta-labeling dataset that sits ON TOP of the mechanical primary
signal (setdw_signal.buy_signal). For every primary BUY(dip) trigger it records:

  • a TRIPLE-BARRIER label — did the underlying reach +1R (upper barrier) before
    its structural stop (llStop, lower barrier) within `vbar` bars (vertical
    barrier)?  1 = win, 0 = stop-first or time-out.
  • the point-in-time FEATURE row (only trailing data as of the signal bar).
  • a LdP sample-UNIQUENESS weight — overlapping ~20-day holds are NOT IID, so
    each label is down-weighted by how many other labels are live over its span
    (AFML Ch.4). Report Σweight ("effective N"), never the raw row count.

Pure on `frames` (ticker -> ascending OHLCV DataFrame), so it runs on either
set_data or yfinance frames. The secondary model, purged-CV validation and live
wiring are Phase 2/3 — this module only produces the labelled dataset.

See .claude/skills/quant-meta-label/SKILL.md and memory quant-knowledge-base
(Pillar 4). Nothing here ships without clearing /quant-validation Gate 5.
"""
import numpy as np
import pandas as pd

import setdw_signal as sig

try:
    import composite as comp_mod
except Exception:                       # pragma: no cover - composite always present in repo
    comp_mod = None

# Feature columns the secondary model consumes. Cross-sectional (z_*, quintile,
# composite) and regime (mkt_vol, risk_off) are NaN when composite is disabled or
# the universe is too small (<5 names) — trees tolerate NaN / neutral gracefully.
FEATURES = ["rsi", "adx", "distPct", "vol_ratio", "riskU_pct",
            "z_mom", "z_trend", "lowvol", "quintile", "composite",
            "mkt_vol", "risk_off", "market"]

_META = ["ticker", "date", "exit_date", "market", "label", "ret_R", "weight"]


def triple_barrier(df, i, stop, t1, vbar):
    """Label the trigger at integer bar position `i` by whichever barrier is hit
    first over the next `vbar` bars.

    Returns (label, exit_pos):
      label 1  -> High >= t1 (upper/take-profit) before any Low <= stop
      label 0  -> Low <= stop (lower/stop) first, OR neither within vbar (time-out)
      (None, None) if there is no forward bar to observe.

    Conservative tie-break: a bar that touches BOTH barriers is scored as a stop
    (label 0) — intrabar path is unknown, so we assume the adverse touch first.
    """
    n = len(df)
    if i + 1 >= n:
        return None, None
    hi = df["High"].values
    lo = df["Low"].values
    end = min(i + vbar, n - 1)
    for k in range(i + 1, end + 1):
        if lo[k] <= stop:               # stop checked first = conservative tie-break
            return 0, k
        if hi[k] >= t1:
            return 1, k
    return 0, end                        # vertical/time barrier = not a win


def let_winners_run_label(df, i, stop, rr1=1.0, maxhold=252):
    """Label the trigger at bar `i` under the LIVE let-winners-run exit — the real
    strategy (set-risk), not a fixed +1R barrier:

      • initial structural stop = `stop` (llStop) until +1R is reached;
      • at Close >= entry + rr1*R the stop moves to BREAKEVEN (entry) — winner armed;
      • thereafter TRAIL: exit on the first Close < EMA20 (no profit cap);
      • `maxhold` bars is a terminal backstop → mark-to-close if still open.

    Returns (label, exit_pos, ret_R) where ret_R is the realized R-multiple at exit
    and label = 1 iff ret_R > 0. Adverse (stop/breakeven) checks precede favorable
    ones each bar (conservative intrabar tie-break). (None,None,None) if unplannable.
    """
    n = len(df)
    if i + 1 >= n:
        return None, None, None
    close = df["Close"].values
    low = df["Low"].values
    ema = df["ema"].values
    entry = float(close[i])
    riskU = entry - stop
    if riskU <= 0:
        return None, None, None
    t1 = entry + rr1 * riskU
    armed = False                                   # breakeven/trail active after +1R
    end = min(i + maxhold, n - 1)
    for k in range(i + 1, end + 1):
        if not armed:
            if low[k] <= stop:                      # structural stop before +1R
                return 0, k, -1.0
            if close[k] >= t1:                      # +1R reached -> arm breakeven, keep holding
                armed = True
                continue
        else:
            if low[k] <= entry:                     # breakeven stop
                return 0, k, 0.0
            if close[k] < ema[k]:                    # trail: closed below EMA20
                r = (float(close[k]) - entry) / riskU
                return int(r > 0), k, r
    r = (float(close[end]) - entry) / riskU          # maxhold backstop: mark-to-close
    return int(r > 0), end, r


def sample_uniqueness(spans, n_bars):
    """LdP average-uniqueness weights for label spans on ONE ticker's timeline.

    spans : list of (start_pos, end_pos) inclusive integer bar positions (the
            actual hold window i+1 .. exit_pos).
    Returns a list of weights in (0, 1]; a label is 1.0 iff no other label
    overlaps ANY bar of its span, and shrinks toward 1/concurrency as overlap
    grows. Concurrency is >=1 everywhere a span exists, so weights never divide
    by zero.
    """
    conc = np.zeros(int(n_bars))
    for s, e in spans:
        conc[s:e + 1] += 1.0
    out = []
    for s, e in spans:
        c = conc[s:e + 1]
        out.append(float(np.mean(1.0 / c)) if len(c) else 1.0)
    return out


def _empty():
    return pd.DataFrame(columns=_META + [c for c in FEATURES if c != "market"])


def build_dataset(frames, cfg=None, signal_fn=None):
    """Build the labelled meta-labeling dataset from `frames`.

    frames : {ticker: OHLCV DataFrame}  (ascending index, Open/High/Low/Close/Volume)
    cfg    : optional dict —
        exit ("barrier") "barrier" = fixed +rr / vbar triple-barrier;
                         "trail"   = live let-winners-run (breakeven at +1R, trail
                                     EMA20, no cap) — the real strategy's label.
        vbar (20)        vertical-barrier length in bars (barrier mode only; shorten
                         for the DW book, Fix 3 — theta bleed; try {10,15,20})
        maxhold (252)    terminal backstop in bars for the trail exit
        rr (RR1=1.0)     upper/breakeven barrier as an R-multiple of riskU
        market (0)       market dummy: 0=SET, 1=US (Fix 1/4 — pool or separate)
        composite (True) attach cross-sectional (z_*, quintile) + regime features
        plus any setdw_signal.buy_signal cfg keys (rsi_min, adx_min, vol_mult ...)
    signal_fn : override the primary (defaults to setdw_signal.buy_signal) —
        used by tests to inject a deterministic trigger.

    Returns a DataFrame with one row per primary trigger:
    [ticker, date, exit_date, market, label, weight, <FEATURES...>].
    Empty (with the right columns) when no trigger fires.
    """
    cfg = dict(cfg or {})
    vbar = int(cfg.get("vbar", 20))
    rr = float(cfg.get("rr", sig.RR1))
    exit_mode = str(cfg.get("exit", "barrier"))     # "barrier" (+rr cap) | "trail" (let-winners-run)
    maxhold = int(cfg.get("maxhold", 252))          # terminal backstop for the trail exit
    market = int(cfg.get("market", 0))
    use_comp = bool(cfg.get("composite", True)) and comp_mod is not None
    signal_fn = signal_fn or sig.buy_signal

    _cs_cache, _exp_cache = {}, {}

    def _cs_row(t, date):
        if not use_comp:
            return None
        if date not in _cs_cache:
            try:
                _cs_cache[date] = comp_mod.cross_section_scores(frames, asof=date)
            except Exception:
                _cs_cache[date] = None
        C = _cs_cache[date]
        if C is None or getattr(C, "empty", True) or t not in C.index:
            return None
        return C.loc[t]

    def _exp(date):
        if not use_comp:
            return None
        if date not in _exp_cache:
            try:
                _exp_cache[date] = sig.exposure_overlay(frames, asof=date)
            except Exception:
                _exp_cache[date] = None
        return _exp_cache[date]

    rows = []
    for t, raw in (frames or {}).items():
        if raw is None or getattr(raw, "empty", True):
            continue
        if len(raw) < sig.SMA_LEN + sig.LOOKBACK:
            continue
        df = sig.add_indicators(raw)
        mask = np.asarray(signal_fn(df, cfg), dtype=bool)
        spans, recs = [], []
        for i in np.where(mask)[0]:
            i = int(i)
            row = df.iloc[i]
            close = float(row["Close"])
            stop = float(row["llStop"])
            riskU = close - stop
            if not (riskU > 0):          # invalid/zero-width stop -> unplannable (trade_plan size=0)
                continue
            if exit_mode == "trail":     # live let-winners-run exit (real strategy)
                label, exit_pos, ret_R = let_winners_run_label(df, i, stop, rr1=rr,
                                                               maxhold=maxhold)
                if label is None:
                    continue
            else:                        # fixed triple-barrier (+rr cap / vbar vertical)
                t1 = close + rr * riskU
                label, exit_pos = triple_barrier(df, i, stop, t1, vbar)
                if label is None:        # no forward bar to observe yet
                    continue
                # Realized R at exit: +rr on a barrier win, -1 on a stop, else
                # mark-to-close at the vertical. entry = signal-bar close (trade_plan `buy`).
                if label == 1:
                    ret_R = rr
                elif float(df["Low"].iloc[exit_pos]) <= stop:
                    ret_R = -1.0
                else:
                    ret_R = (float(df["Close"].iloc[exit_pos]) - close) / riskU
            ema = float(row["ema"])
            vol_sma = float(row["volSma"]) if pd.notna(row["volSma"]) else np.nan
            rec = {
                "ticker": t, "date": df.index[i], "exit_date": df.index[exit_pos],
                "market": market, "label": int(label), "ret_R": float(ret_R),
                "rsi": float(row["rsi"]), "adx": float(row["adx"]),
                "distPct": (close - ema) / ema * 100 if ema else np.nan,
                "vol_ratio": float(row["Volume"]) / vol_sma if vol_sma else np.nan,
                "riskU_pct": riskU / close * 100 if close else np.nan,
                "z_mom": np.nan, "z_trend": np.nan, "lowvol": np.nan,
                "quintile": np.nan, "composite": np.nan,
                "mkt_vol": np.nan, "risk_off": np.nan,
            }
            cr = _cs_row(t, df.index[i])
            if cr is not None:
                for k in ("z_mom", "z_trend", "lowvol", "quintile", "composite"):
                    v = cr.get(k, np.nan) if hasattr(cr, "get") else np.nan
                    rec[k] = float(v) if pd.notna(v) else np.nan
            ex = _exp(df.index[i])
            if ex is not None:
                mv = ex.get("mkt_vol")
                rec["mkt_vol"] = float(mv) if mv is not None else np.nan
                rec["risk_off"] = 1.0 if ex.get("risk_off") else 0.0
            spans.append((i + 1, exit_pos))
            recs.append(rec)
        if recs:
            for r_, w in zip(recs, sample_uniqueness(spans, len(df))):
                r_["weight"] = w
            rows.extend(recs)

    if not rows:
        return _empty()
    out = pd.DataFrame(rows)
    cols = _META + [c for c in FEATURES if c != "market"]
    return out.reindex(columns=cols)


def effective_n(dataset):
    """LdP effective sample size = Σ uniqueness weight (Fix 1). Report this, not
    len(dataset) — overlapping 20-day labels make the raw count optimistic."""
    if dataset is None or len(dataset) == 0 or "weight" not in dataset:
        return 0.0
    return float(dataset["weight"].sum())


def summary(dataset):
    """Quick sanity dict: rows, effective N, win rate (unweighted & weighted),
    date span. Weighted win rate is the honest base rate for the secondary."""
    if dataset is None or len(dataset) == 0:
        return {"rows": 0, "eff_n": 0.0, "win": None, "win_w": None,
                "start": None, "end": None}
    w = dataset["weight"]
    y = dataset["label"]
    r = dataset["ret_R"] if "ret_R" in dataset else None
    return {
        "rows": int(len(dataset)),
        "eff_n": round(effective_n(dataset), 1),
        "win": round(float(y.mean()), 4),
        "win_w": round(float((y * w).sum() / w.sum()), 4) if w.sum() else None,
        "exp_R": round(float((r * w).sum() / w.sum()), 4) if r is not None and w.sum() else None,
        "start": str(dataset["date"].min()),
        "end": str(dataset["date"].max()),
    }


# --------------------------------------------------------------------------- #
# CLI — real 12y build over a universe via yfinance (kept out of import path so
# tests stay offline). Usage:
#   python meta_label.py --universe set100.bk.txt --years 12 --market 0 \
#       --out reports/meta_dataset_set.csv
# --------------------------------------------------------------------------- #
def _load_yf(universe_path, years):                # pragma: no cover - network
    import yfinance as yf
    with open(universe_path) as f:
        tickers = [x.split("#")[0].strip() for x in f if x.split("#")[0].strip()]
    frames = {}
    for i, t in enumerate(tickers):
        try:
            df = yf.download(t, period=f"{years}y", interval="1d",
                             progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df is not None and len(df) >= sig.SMA_LEN + sig.LOOKBACK:
                frames[t] = df
        except Exception as e:
            print(f"  skip {t}: {str(e)[:50]}")
        if (i + 1) % 20 == 0:
            print(f"  fetched {i + 1}/{len(tickers)} ...")
    return frames


def main(argv=None):                               # pragma: no cover - CLI glue
    import argparse
    ap = argparse.ArgumentParser(description="Build the meta-labeling dataset (Phase 1).")
    ap.add_argument("--universe", required=True, help="one ticker per line (yfinance symbols)")
    ap.add_argument("--years", type=int, default=12)
    ap.add_argument("--exit", choices=["barrier", "trail"], default="barrier",
                    help="barrier=+rr/vbar cap | trail=live let-winners-run")
    ap.add_argument("--vbar", type=int, default=20)
    ap.add_argument("--maxhold", type=int, default=252)
    ap.add_argument("--rr", type=float, default=sig.RR1)
    ap.add_argument("--market", type=int, default=0, help="0=SET, 1=US")
    ap.add_argument("--no-composite", action="store_true")
    ap.add_argument("--out", default="reports/meta_dataset.csv")
    a = ap.parse_args(argv)
    frames = _load_yf(a.universe, a.years)
    cfg = {"exit": a.exit, "vbar": a.vbar, "maxhold": a.maxhold, "rr": a.rr,
           "market": a.market, "composite": not a.no_composite}
    ds = build_dataset(frames, cfg)
    ds.to_csv(a.out, index=False)
    print(f"wrote {a.out}")
    print("summary:", summary(ds))
    return ds


if __name__ == "__main__":                         # pragma: no cover
    main()
