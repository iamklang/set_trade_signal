---
name: set-evidence
description: >-
  Backtest evidence and research base for the SET DW Swing system — what
  survived testing (and what didn't), honest limitations, academic support.
  Use when the user asks "does this strategy work", wants backtest results,
  or questions the edge. Part of the SET DW Swing system.
---

# SET DW Swing — Evidence Base

What research and backtesting support (and don't) about the mechanical core.
Use this to weight conviction — these are about base rates, not any single
trade.

## What actually survived testing (CORE CONCEPT)

After stress-testing every tempting idea on BOTH a 10y and 5y window:

**Validated core:**
- Buy-the-dip (mean-reversion) entry
- Composite mom+trend leader ranking
- Let-winners-run exit (breakeven at +1R, trail the EMA after, no target cap)
- ~12-name cap
- Composite-quintile position sizing (Q1 1.5× … Q5 0.5×)
- Below-200-SMA regime brake
- Patient limit execution on liquid names
- Lot size = 100 shares (SET board lot)

**Sounded good but tested NEGATIVE (rejected):**
- Switching entry to breakout only (great on 10y, collapses on 5y — survivorship/regime)
- `dip∩breakout` and `dip∪breakout` (worse or fragile)
- Vol-target / drawdown / regime *exposure overlays* (de-risk away return, no free Sharpe)
- Fractional-Kelly / inverse-vol sizing (backfires: high-vol names ARE the high-edge leaders)
- `close < EMA` exit before +1R (cut ~84% of trades early, PF 0.75 — net loser)
- CDC ActionZone entry (failed 5y OOS backtest)

## Key numbers

| Metric | Value |
|---|---|
| PF (per-trade, let-run) | 1.26 (+0.93%/trade) |
| PF with Q1 filter | 1.34 (+1.33%/trade) |
| Win rate (with momentum gate) | ~61% |
| Portfolio CAGR (best config) | ~5% |
| Max drawdown | −30% to −41% |
| Position cap sweet spot | ~12 names |

## Cost & execution findings

- **Patient LIMIT trader** (rest at the touch): Sharpe ~0.6
- **Market TAKER** (cross the spread): Sharpe halves
- **Thin 2-tick names**: PF < 1 (edge dies)
- Execution style + name liquidity matter MORE than the signal
- Always place a limit at the signal close — never chase a gap up

## Academic evidence on the SET

- **EMA/trend rules are net-profitable after costs on the SET** (emerging
  market), unlike most developed markets. *(Tharavanij 2015; Fifield 2008)*
- The edge comes from **catching big trends, not precise timing** — ride
  winners; don't over-trust pinpoint dip entries.
- Across 92 studies, TA results are "mostly positive but methodologically
  flawed" and shrink with realistic costs. *(Park & Irwin 2004)*
- **DW implied volatility on the SET is biased (inflated)** — DWs are
  structurally priced rich; holding time is a cost. *(ScienceDirect)*
- **IV crush is real around earnings.** *(IFEC; ipresage)*

## Honest limitations

- **Survivorship bias**: all tested names survived to today — live results are
  likely worse.
- DW leverage/IV/theta not modeled (would amplify losses).
- The chart mechanics alone don't pay — any real edge requires the
  discretionary macro/sector/earnings layer plus disciplined sizing.
- Per-stock optimization (DELTA/RCL/HANA) holds OOS but sample sizes are
  small.
- Not verified on the SET specifically: PEAD, sector-rotation drivers
  (oil/baht/foreign-flow), the 1%/2R sizing numbers.
- The earnings peer read-through and "who carries" theses remain the trader's
  inference.
- TA studies span ~1989–2013; market microstructure has since changed.

## The bottom line

The edge is **thin, real, and right-tailed** — many small losers, a few big
winners. It is NOT a money machine. Protecting the edge (cost, liquidity,
no-overfit, sitting through losers) matters more than adding cleverness.

## Backtest scripts

| Script | Tests |
|---|---|
| `bt_portfolio.py` | Portfolio-level: sizing, cap sweep, cost models |
| `bt_exits.py` | Exit rules comparison (V1-V5) |
| `bt_composite.py` | Walk-forward quintile test |
| `bt_weekly.py` | 1-week horizon: V5 vs weekly variants |
| `bt_triggers.py` | Bull-scan triggers vs strict BUY(dip) |
| `bt_holdout.py` | Time-split holdout: overfitting check |
| `bt_quality.py` | ROE quality factor improvement test |

## When to use

- "Does this strategy actually work?"
- "Show me backtest results"
- "What's the edge? What's the win rate?"
- "What was tested and rejected?"
- "Is the evidence solid?"
