"""
costs.py — first-principles SET transaction-cost model.

The Medallion research (medallion-research.md) flags transaction cost as FIRST-ORDER and says to
model the ACTUAL bid-ask half-spread, not a generic flat %. Our backtests used a flat 0.3%/side;
on the SET the *quoted* spread is set by the exchange tick-size table and is price-dependent — for
most names it works out LARGER than 0.3% once you add commission, so flat 0.3% is optimistic.

Per-side cost a taker pays vs mid  =  commission  +  half the quoted spread.
Quoted spread (tightest, liquid name) = 1 tick; thin names quote wider (spread_ticks > 1).

This is EOD-compatible (needs only the fill price) and shared by the backtests and (optionally)
the live trade_plan. NOT a live-quote feed — a structural floor from the exchange rules.
"""

# SET tick-size (min price step) table: (price_upper_exclusive, tick). Source: SET board-lot /
# spread rules. Below 2 THB the tick is 0.01; it steps up by price band to 2.00 above 400.
_TICKS = [
    (2.0, 0.01), (5.0, 0.02), (10.0, 0.05), (25.0, 0.10),
    (100.0, 0.25), (200.0, 0.50), (400.0, 1.00), (float("inf"), 2.00),
]

# Online SET commission ~0.157%/side (broker + fees; VAT on commission is a rounding add). This
# is the same figure the .pine strategy used, kept as the default so results stay comparable.
COMMISSION = 0.00157

# US retail model: ~$0 commission (zero-commission brokers) + a penny (0.01) quote tick. Liquid
# S&P 500 names quote ~1 penny wide, so the half-spread is ~$0.005 relative to price — far cheaper
# than the SET. Selected automatically for the US market profile (market.cost_mode() == "us").
US_COMMISSION = 0.0
US_TICK = 0.01


def _active_cost_mode():
    """The active market's cost model ('set' default). Imported lazily to avoid any import
    ordering concerns; falls back to 'set' if the profile module is unavailable."""
    try:
        import market
        return market.cost_mode()
    except Exception:
        return "set"


def set_tick(price):
    """The SET minimum tick (price step) for a given price."""
    for hi, t in _TICKS:
        if price < hi:
            return t
    return 2.00


def half_spread_frac(price, spread_ticks=1.0):
    """Half the quoted spread as a fraction of price. `spread_ticks` = the quoted spread measured
    in ticks: 1.0 = tightest (liquid SET100 name), >1 for thin names / DWs that quote wider. A
    patient limit order that rests at the touch can pay ~0 of this; a market taker pays it all."""
    if price is None or price <= 0:
        return 0.0
    return 0.5 * spread_ticks * set_tick(price) / price


def us_half_spread_frac(price, spread_ticks=1.0):
    """Half the quoted spread as a fraction of price under the US penny-tick model."""
    if price is None or price <= 0:
        return 0.0
    return 0.5 * spread_ticks * US_TICK / price


def side_cost(price, spread_ticks=1.0, commission=None, mode=None):
    """Per-SIDE cost fraction a taker pays vs mid: commission + half the quoted spread. Round-trip
    ≈ 2×. Use spread_ticks=0 to model perfect limit-order fills (commission only). `mode` selects
    the market cost model ('set'/'us'); None → the active market profile. Backward compatible: an
    explicit `commission` overrides the model default."""
    mode = mode or _active_cost_mode()
    if mode == "us":
        c = US_COMMISSION if commission is None else commission
        return c + us_half_spread_frac(price, spread_ticks)
    c = COMMISSION if commission is None else commission
    return c + half_spread_frac(price, spread_ticks)


def trailing_turnover(df, window=20, asof=None):
    """Latest trailing-median daily turnover (THB = Close × Volume) for a name, or None if the
    frame is too short. The liquidity metric the ฿-floor gate uses. `asof` (a Timestamp) slices
    to that bar first so a historical scan/backtest sees point-in-time liquidity."""
    if df is None or "Close" not in getattr(df, "columns", []) or "Volume" not in df.columns:
        return None
    d = df if asof is None else df[df.index <= asof]
    if len(d) < window:
        return None
    try:
        return float((d["Close"] * d["Volume"]).rolling(window).median().iloc[-1])
    except (KeyError, IndexError, ValueError):
        return None


def spread_ticks_for(turnover):
    """Estimate a name's quoted spread (in ticks) from its trailing daily turnover (THB value
    traded). Very liquid names quote at the touch and are often mid-fillable; thin names quote
    2+ ticks wide — and the bt_portfolio cost experiment showed a 2-tick spread KILLS the edge.
    NaN/unknown -> 1.5 (mid). Buckets are deliberately coarse (a structural estimate, not tuned)."""
    if turnover is None or turnover != turnover:      # None or NaN
        return 1.5
    if turnover >= 100e6:
        return 0.5
    if turnover >= 20e6:
        return 1.0
    if turnover >= 5e6:
        return 1.5
    return 2.0
