"""
setdw_signal — single source of truth for the SET DW Swing "BUY (dip)" signal.

Mirrors the defaults of set-dw-swing.pine / set-dw-swing-strategy.pine so the
scanner (scan_dip.py) and the backtest (bt_maxext.py) can never drift apart.

Signal (all on the same, fully-closed bar):
    trendUp  = close>EMA20 & EMA rising & EMA>SMA200 & SMA200 rising(>=sma[5])
    freshDip = lowest(low,5) <= EMA*(1+prox) AND low[1] <= EMA[1]*(1+prox)
    green    = close>open & close>=high[1]
    momentum = RSI(14) >= rsiMin (55)
    trend    = ADX(14) >= adxMin (20)
    volConf  = Volume > volSMA(20)        [default ON — PF 1.10->1.13]
    [optional, default OFF] redPrior, maxExt
"""
import pandas as pd
import numpy as np

# Defaults identical to the .pine inputs
EMA_LEN, SMA_LEN = 20, 200
PROX = 0.015          # pullback proximity to EMA (1.5%)
LOOKBACK = 5          # dip lookback (bars)
STOPLOOK = 10         # structural swing-low lookback
RSI_MIN, ADX_MIN = 55, 20
RR1, RR2 = 1.0, 1.5   # R-multiple targets


def wilder(s, n):
    """Wilder's smoothing (RMA) — matches TradingView ta.rsi / ta.dmi internals."""
    return s.ewm(alpha=1 / n, adjust=False).mean()


def add_indicators(df):
    """Attach every column the signal needs. Expects OHLCV columns
    Open/High/Low/Close/Volume (yfinance style). Returns the same df."""
    df = df.copy()
    c, h, l = df["Close"], df["High"], df["Low"]
    df["ema"] = c.ewm(span=EMA_LEN, adjust=False).mean()
    df["sma"] = c.rolling(SMA_LEN).mean()
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    # RSI(14), Wilder
    d = c.diff()
    rs = wilder(d.clip(lower=0), 14) / wilder(-d.clip(upper=0), 14)
    df["rsi"] = 100 - 100 / (1 + rs)
    # ADX(14), Wilder DMI
    up, dn = h.diff(), -l.diff()
    plusDM = np.where((up > dn) & (up > 0), up, 0.0)
    minusDM = np.where((dn > up) & (dn > 0), dn, 0.0)
    atrw = wilder(tr, 14)
    plusDI = 100 * wilder(pd.Series(plusDM, index=df.index), 14) / atrw
    minusDI = 100 * wilder(pd.Series(minusDM, index=df.index), 14) / atrw
    dx = 100 * (plusDI - minusDI).abs() / (plusDI + minusDI).replace(0, np.nan)
    df["adx"] = wilder(dx, 14)
    # Structure / dip / confirmation
    df["llStop"] = l.rolling(STOPLOOK).min()
    df["llLook"] = l.rolling(LOOKBACK).min()
    df["emaUp"] = df["ema"] >= df["ema"].shift(1)
    df["smaUp"] = df["sma"] >= df["sma"].shift(5)
    df["volSma"] = df["Volume"].rolling(20).mean()
    df["green"] = (c > df["Open"]) & (c >= h.shift(1))
    df["freshprior"] = l.shift(1) <= df["ema"].shift(1) * (1 + PROX)
    return df


def buy_signal(df, cfg=None):
    """Boolean Series: True on bars where the BUY (dip) setup is confirmed.
    cfg keys (all optional, default to the .pine defaults):
        rsi_min, rsi_max (upper RSI cap, default 100 = no cap), adx_min,
        maxext (%, 0=off, default off), need_vol_conf (default ON),
        vol_mult (volume floor = volSMA*vol_mult, default 1.0), need_red_prior (default off)."""
    cfg = cfg or {}
    rsi_min = cfg.get("rsi_min", RSI_MIN)
    rsi_max = cfg.get("rsi_max", 100)        # no upper cap by default
    adx_min = cfg.get("adx_min", ADX_MIN)
    maxext = cfg.get("maxext", 0.0)
    vol_mult = cfg.get("vol_mult", 1.0)
    c = df["Close"]
    trendUp = (c > df["ema"]) & df["emaUp"] & (df["ema"] > df["sma"]) & df["smaUp"]
    freshDip = (df["llLook"] <= df["ema"] * (1 + PROX)) & df["freshprior"]
    b = (trendUp & freshDip & df["green"]
         & (df["rsi"] >= rsi_min) & (df["rsi"] <= rsi_max) & (df["adx"] >= adx_min))
    if cfg.get("need_red_prior"):
        b = b & (c.shift(1) < df["Open"].shift(1))
    if cfg.get("need_vol_conf", True):   # default ON (mirrors .pine) — PF 1.10->1.13
        b = b & (df["Volume"] > df["volSma"] * vol_mult)   # vol_mult>1 = demand a vol surge
    if maxext and maxext > 0:
        b = b & (c <= df["ema"] * (1 + maxext / 100))
    return b.fillna(False)


def _num(x):
    """Coerce to float, or None when missing/NaN/non-numeric."""
    try:
        v = float(x)
        return v if pd.notna(v) else None
    except (TypeError, ValueError):
        return None


# Live status precedence for sorting a holdings list (best -> worst).
STATUS_RANK = {"T2": 0, "T1": 1, "HOLD": 2, "WEAK": 3, "STOP": 4, "?": 5}


def live_status(df, entry, stop, t1, t2):
    """Classify a prior BUY(dip) hit on the LATEST closed bar — is it still holdable?
    Returns {cur, pl_pct, status} where status is:
      STOP  close <= stop (stopped out)        T2  close >= t2 (target 2 hit)
      T1    close >= t1 (target 1 hit)         HOLD close > EMA20 AND close > entry
      WEAK  above stop but lost EMA20 or       ?   insufficient data
            still below entry (underwater)
    Precedence stop > t2 > t1 > (ema & entry) so a stop-out is never masked by a stale
    target, and HOLD demands BOTH trend intact (above EMA20) AND in profit (above entry)."""
    out = {"cur": None, "pl_pct": None, "status": "?"}
    if df is None or len(df) < EMA_LEN + 5:
        return out
    row = add_indicators(df).iloc[-1]
    cur, ema = float(row["Close"]), float(row["ema"])
    entry, stop, t1, t2 = _num(entry), _num(stop), _num(t1), _num(t2)
    out["cur"] = cur
    if entry:
        out["pl_pct"] = (cur - entry) / entry * 100
    if stop is not None and cur <= stop:
        out["status"] = "STOP"
    elif t2 is not None and cur >= t2:
        out["status"] = "T2"
    elif t1 is not None and cur >= t1:
        out["status"] = "T1"
    elif cur > ema and (entry is None or cur > entry):
        out["status"] = "HOLD"
    else:
        out["status"] = "WEAK"
    return out


def trade_plan(row, equity, risk_pct, rr1=RR1, rr2=RR2):
    """Given a signal row (a df row with Close/ema/llStop/rsi/adx), return the
    §7 entry plan: stop, risk/unit, T1, T2, size, dist%."""
    close = float(row["Close"])
    stop = float(row["llStop"])
    risk_u = close - stop
    size = int(np.floor((equity * risk_pct / 100) / risk_u)) if risk_u > 0 else 0
    return {
        "close": close,
        # Next-day entry: the signal-bar close is the reference the whole plan (stop/target/
        # size) is built on — place a limit at this price OR BETTER next session; don't chase a
        # gap up (that breaks the R-multiples). Kept as its own field so it flows to the CSV /
        # positions / alert as the actionable order price.
        "buy": close,
        "stop": stop,
        "riskU": risk_u,
        "t1": close + rr1 * risk_u,
        "t2": close + rr2 * risk_u,
        "size": size,
        "distPct": (close - float(row["ema"])) / float(row["ema"]) * 100,
        "rsi": float(row["rsi"]),
        "adx": float(row["adx"]),
    }


# Composite-quintile POSITION-SIZE tilt. bt_portfolio.py (2026-07-03) showed that scaling
# each position by its composite (mom+trend) quintile beat equal-weight on Sharpe AND profit
# factor in BOTH the 10y and 5y windows (quintile-tier was the winner — best Sharpe/PF with a
# milder drawdown than an aggressive linear tilt). Q1(top leaders) oversized, Q5 undersized.
QUINTILE_SIZE_MULT = {1: 1.5, 2: 1.25, 3: 1.0, 4: 0.75, 5: 0.5}


def size_mult_for(quintile):
    """Position-size multiplier for a composite quintile (1=top). Unknown/None -> 1.0 neutral
    (e.g. when the composite ranking is unavailable — the scan ran without --composite)."""
    try:
        return QUINTILE_SIZE_MULT.get(int(quintile), 1.0)
    except (TypeError, ValueError):
        return 1.0


def apply_size_tilt(plan, quintile, regime_mult=1.0):
    """Scale a trade_plan's `size` by the composite-quintile tilt AND the market-regime brake,
    IN PLACE (size = base × quintile_mult × regime_mult), recording size_base/size_mult/
    regime_mult/quintile. Re-tiltable — always recomputes from the stored base so repeated
    calls never compound. Returns the plan."""
    base = plan.get("size_base", plan.get("size", 0)) or 0
    mult = size_mult_for(quintile)
    plan["size_base"] = base
    plan["size_mult"] = mult
    plan["regime_mult"] = regime_mult
    plan["size"] = int(np.floor(base * mult * regime_mult))
    plan["quintile"] = quintile
    return plan


# Market-regime brake. bt_portfolio.py (2026-07-04) — halving new-entry exposure when the
# equal-weight universe index is below its 200-SMA cut maxDD ~9pts on both the 10y and 5y
# windows while ~holding 10y return; a risk-off drawdown guard for the leveraged DW context.
REGIME_RISK_OFF_MULT = 0.5


def market_regime(frames, asof=None, sma_len=SMA_LEN):
    """Equal-weight-universe regime: is the index below its 200-SMA (risk-off)? Returns
    {risk_off, factor, index, sma}; factor = REGIME_RISK_OFF_MULT when risk-off else 1.0.
    Missing/short data -> risk-on (factor 1.0) so a data gap never brakes sizing."""
    closes = {}
    for t, df in frames.items():
        if df is None or not hasattr(df, "columns") or "Close" not in df.columns:
            continue
        s = df["Close"]
        if asof is not None:
            s = s[s.index <= asof]
        if len(s):
            closes[t] = s
    off = {"risk_off": False, "factor": 1.0, "index": None, "sma": None}
    if not closes:
        return off
    px = pd.DataFrame(closes).sort_index()
    idx = (1 + px.pct_change().mean(axis=1).fillna(0)).cumprod()
    if len(idx) < sma_len + 1:
        return off
    sma = idx.rolling(sma_len).mean()
    iv, sv = float(idx.iloc[-1]), sma.iloc[-1]
    if pd.isna(sv):
        return off
    risk_off = iv < float(sv)
    return {"risk_off": bool(risk_off),
            "factor": REGIME_RISK_OFF_MULT if risk_off else 1.0,
            "index": iv, "sma": float(sv)}


def load_market_regime(path, max_age_h=48):
    """Read a market_regime.json (written by scan_dip's market_regime()) -> (factor, age_hours).
    Returns (1.0, age) if the file is missing, older than max_age_h, or unreadable — a stale or
    absent regime read must fall back to NO brake rather than silently trusting a frozen factor
    forever (e.g. the scan job stopped running). Shared by alert.py and scan_bull.py so both
    apply the identical freshness contract as composite_rank.csv."""
    import json as _json
    import os as _os
    import time as _time
    if not _os.path.exists(path):
        return 1.0, None
    age_h = (_time.time() - _os.path.getmtime(path)) / 3600
    if max_age_h and age_h > max_age_h:
        return 1.0, age_h
    try:
        factor = float(_json.load(open(path)).get("factor", 1.0))
    except (OSError, ValueError, KeyError):
        return 1.0, age_h
    return factor, age_h
