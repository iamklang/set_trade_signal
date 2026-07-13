---
name: set-risk
description: >-
  Risk management, position sizing, and exit rules for the SET DW Swing system
  — fixed-fractional sizing (lot 100), R-multiples, let-winners-run lifecycle
  (breakeven at T1, trail EMA after, no cap), position cap, composite-quintile
  tilt, regime brake, rotation, cooldown. Use when the user asks about sizing,
  stops, exit rules, position management, or "how much to buy". Part of the
  SET DW Swing system (see also: /set-entry, /set-macro).
---

# SET Risk Management & Position Lifecycle

The exit and sizing rules that actually survived backtesting on SET100 (10y +
5y). How you size and exit matters more than the entry signal.

> Not financial advice. The edge is thin and right-tailed — many small losers,
> a few big winners.

## Position sizing

### Fixed-fractional risk sizing

Risk a fixed **~1% (max 2%)** of equity per trade. Back into size from the
stop distance:

```
size = (equity × risk%) ÷ (entry − stop)
```

- Round down to **multiples of 100** (SET board lot).
- Cap at `equity ÷ entry` (can't buy more than capital allows).
- Size from **available capital** (equity − committed), not total equity.

### Composite-quintile tilt

Scale size by composite ranking (momentum + trend):

| Quintile | Multiplier |
|---|---|
| Q1 (top leaders) | 1.5× |
| Q2 | 1.25× |
| Q3 | 1.0× |
| Q4 | 0.75× |
| Q5 | 0.5× |

This beat equal-weight on Sharpe AND profit factor in both test windows.

### Market-regime brake

When the broad index is **below its 200-SMA** (risk-off), **halve new position
size**. This trims max drawdown ~9pts — a cheap drawdown guard that matters
most with leveraged DWs.

## R-multiples

Define **1R = your stop distance** (the amount at risk). Judge every trade by
reward-to-risk *before* entering — take setups offering **≥ 2R–3R**.

Track outcomes in R so expectancy = `(avg win × win%) − (avg loss × loss%)`
stays positive over many trades.

## Position lifecycle (let-winners-run)

```
BUY(dip/brk)      close >= T1 (+1R)                 close < EMA20 or stop
  │ enter FULL      │ stop → breakeven, let run       │ exit
  ▼                 ▼                                 ▼
HOLDING/FULL ────▶ HOLDING/RUN ──────────────────▶ SELL_FLAGGED → dropped
  └─ close <= stop ─────────────────────────────▶ SELL_FLAGGED → dropped
```

### Key rules

- **FULL phase** (before T1): exit ONLY on structural stop. Do NOT exit on
  close < EMA — that rule cut ~84% of trades early and made the book a net
  loser (PF 0.75).
- **At +1R (T1)**: move stop to breakeven. Now it can't lose money.
- **RUN phase** (after T1): **no take-profit cap** — let it run until it loses
  the 20-EMA or hits the (breakeven) stop. Capping at T2 threw away the right
  tail.
- **Trailing exit**: close < EMA20 (only after T1) or close ≤ stop.

### Sell reasons

| Code | Meaning |
|---|---|
| STOP | Hit structural stop (before T1) — full loss |
| BE | Hit breakeven stop (after T1) — scratch trade |
| TRAIL | Closed below EMA20 (after T1) — take profit |
| ROTATE | Replaced by a stronger candidate |

## Position cap & rotation

- **Cap at ~12 concurrent names** — tighter caps over-concentrate (→ −48% DD);
  wider ones idle cash.
- When full, a weaker new hit is **skipped**; an over-cap holding **rotates
  out** (weakest composite score exits).
- **Smart rotation**: if a new entry has upside-to-T1 > weakest incumbent +5%,
  auto-flag the old one for sell.

## Cooldown

**5 trading sessions** after a full exit before the same name can re-enter.
Prevents whipsaw re-entry the backtest never modeled.

## Exposure overlay

```
position size × voltgt × ddbrake
```

- **voltgt**: target portfolio volatility ~18%
- **ddbrake**: halve exposure when drawdown from equity peak ≥ 12%

## Capital discipline

- Don't tie capital up in chased positions ("ดอย") and miss better setups.
- **Tranche in (`ไม้ 2 ไม้ 3`):** scale entries — a first lot at the base, a
  2nd/3rd "insurance" lot at deeper support — instead of one all-in buy.
- **Never average down a losing leveraged position.** A pre-planned tranche-in
  at support is fine; rescuing a position that broke its stop is not.
- **Hedge by switching sides:** flip to puts if the macro flips.

## When to use

- "How much to buy? What size?"
- "Exit rules — when do I sell?"
- "Position management for my holdings"
- "What's the R-multiple on this trade?"
- "Book is full — should I rotate?"
