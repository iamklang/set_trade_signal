"""
composite.py — cross-sectional multi-factor score for ranking a SET universe.

The daily BUY(dip) trigger (setdw_signal.buy_signal) is a SINGLE-NAME timing signal;
on its own the mechanical core backtests ~break-even (see the project's backtest notes).
The deep-research pass (multi-factor evidence) says the real, evidenced edge comes from
RANKING names cross-sectionally on a blend of factors and trading only the leaders:

  • Momentum (12-1)  — Jegadeesh-Titman / Moskowitz-Ooi-Pedersen: past 12m return
                       skipping the most recent month (skip avoids 1-month reversal).
  • Trend            — distance of price above its SMA200 (are we in an uptrend now?).
  • Low-volatility   — inverse realised vol; a price-based QUALITY/defensive proxy that
                       empirically cuts momentum-crash drawdown (mom+trend+low-vol blend).

Each factor is turned into a cross-sectional z-score ACROSS THE UNIVERSE on a given bar,
then averaged (equal weight by default) into `composite`. Higher = stronger trend leader.
This is a bottom-up composite (average of standardised factor scores), which the S&P DJI
multi-factor research finds beats a top-down "index of indices" by not diluting exposure.

Quality proper (ROE / gross-profitability / q-factor — the factor with ~2x significance on
the SET per Charoenwong-Nettayanun-Saengchote 2021) needs FUNDAMENTAL data that set_data
does not fetch; `raw_factors` leaves a documented hook (`quality=None`) so it can slot in
later without changing the blend logic.

Price-only, so it runs on either set_data or Yahoo frames. Used by scan_dip.py (live
top-quintile filter) and scratchpad/bt_composite.py (walk-forward quintile backtest).
"""
import numpy as np
import pandas as pd

# Factor lookbacks (trading days). 12-1 momentum = return from ~12mo ago to ~1mo ago.
MOM_LOOK = 252          # ~12 months
MOM_SKIP = 21           # ~1 month skipped (avoid short-term reversal)
TREND_LOOK = 200        # SMA200 trend reference
VOL_LOOK = 120          # ~6 months realised-vol window
MIN_BARS = MOM_LOOK + MOM_SKIP + 5      # history needed before a name is scorable

Z_CLIP = 3.0                            # winsorize z-scores to ±3 (guards against outliers)
FACTORS = ("mom", "trend", "lowvol")    # quality slots in here once fundamentals exist
# SET100 12y walk-forward (scratchpad/bt_composite.py): mom+trend is the effective
# SELECTION blend — Q1 CAGR 20.4% / Sharpe 1.02 / PF 2.36 / net 18.8%, beating both
# momentum-only (17.6% / 0.91) and the +low-vol full blend (16.6% / 1.04). Adding low-vol
# as a *selection* factor dilutes return and muddies the bottom quintile; the evidence says
# low-vol/vol-scaling belongs in POSITION SIZING (crash overlay), not name selection. So the
# default weights low-vol at 0 (still computed & available via explicit weights for sizing).
DEFAULT_WEIGHTS = {"mom": 1.0, "trend": 1.0, "lowvol": 0.0}


def raw_factors(df, quality=None):
    """Raw factor values on the LAST bar of `df` (a single name's OHLCV, ascending).
    Returns a dict {mom, trend, lowvol[, quality]} or None if history is too short.
    `quality` (optional) is a pre-fetched fundamental score (e.g. ROE) passed straight
    through — the hook for adding the q-factor later without touching callers."""
    c = df["Close"].dropna()
    if len(c) < MIN_BARS:
        return None
    mom = c.iloc[-(MOM_SKIP + 1)] / c.iloc[-(MOM_LOOK + 1)] - 1.0
    sma = c.iloc[-TREND_LOOK:].mean()
    trend = c.iloc[-1] / sma - 1.0 if sma > 0 else np.nan
    rets = c.pct_change().dropna()
    vol = rets.iloc[-VOL_LOOK:].std() * np.sqrt(252)
    out = {"mom": mom, "trend": trend, "lowvol": -vol}   # -vol so higher = calmer = better
    if quality is not None:
        out["quality"] = float(quality)
    return out


def cross_section_scores(frames, asof=None, weights=None, quality=None):
    """Rank a universe cross-sectionally on the composite factor blend.

    frames : {ticker: DataFrame}  (set_data.fetch_all / yfinance style, ascending index)
    asof   : pd.Timestamp — trim each frame to bars <= asof (point-in-time). None = latest.
    weights: dict per factor (default equal). Only factors present for ALL names are used.
    quality: optional {ticker: score} fundamental map; names missing it just skip that factor.

    Returns a DataFrame indexed by ticker with the raw factors, their z-scores (z_*),
    `composite`, `rank` (1 = best) and `quintile` (1 = top 20%, 5 = bottom), sorted best-first.
    Empty DataFrame if fewer than 5 names are scorable."""
    rows = {}
    for t, df in (frames or {}).items():
        if df is None or getattr(df, "empty", True):
            continue
        d = df if asof is None else df[df.index <= asof]
        q = None if quality is None else quality.get(t)
        rf = raw_factors(d, quality=q)
        if rf is not None:
            rows[t] = rf
    if len(rows) < 5:
        return pd.DataFrame()

    R = pd.DataFrame(rows).T.astype(float)
    weights = dict(weights or DEFAULT_WEIGHTS)
    # blend every non-zero-weight factor that has enough coverage. z-score over the names
    # that HAVE the factor; names missing it (e.g. quality with no reported ROE) get z=0
    # (neutral) so a partial factor still contributes without dropping the whole column.
    num = pd.Series(0.0, index=R.index)
    den = 0.0
    for f in weights:
        w = weights[f]
        if not w or f not in R.columns:
            continue
        col = pd.to_numeric(R[f], errors="coerce")
        valid = col.notna()
        if valid.sum() < max(3, int(0.5 * len(R))):   # <50% coverage (min 3) -> skip factor
            continue
        mu, sd = col[valid].mean(), col[valid].std()
        z = (col - mu) / sd if sd and sd > 0 else pd.Series(0.0, index=R.index)
        # Winsorize: on a ~100-name universe one runaway name (e.g. a +150% squeeze) drags
        # the whole cross-section's mean/sd and distorts every OTHER name's quintile; bounding
        # factor scores is the standard guard (clipped z / bounded tilts improve OOS stability).
        z = z.clip(-Z_CLIP, Z_CLIP)
        R["z_" + f] = z.fillna(0.0)                     # missing -> neutral
        num = num + R["z_" + f] * w
        den += abs(w)
    if den == 0:
        return pd.DataFrame()
    R["composite"] = num / den

    R = R.sort_values("composite", ascending=False)
    n = len(R)
    R["rank"] = range(1, n + 1)
    R["quintile"] = ((R["rank"] - 1) * 5 // n + 1).clip(1, 5)
    return R
