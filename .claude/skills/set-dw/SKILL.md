---
name: set-dw
description: >-
  DW (derivative warrant) selection for SET trading — effective gearing, delta/
  moneyness, implied volatility, theta, IV crush, series naming. Use when the
  user wants to pick which DW series to trade, compare DW choices, or
  understand DW mechanics. Part of the SET DW Swing system (see also:
  /set-entry, /set-earnings, /set-risk).
---

# SET DW (Derivative Warrant) Selection

Expert-grounded guide to picking the right DW series. The trader's rules
(liquid, "sen" ≥ 0.8, gearing 3.5–5.7×, far expiry) are a starting point;
what actually governs your return is more precise.

> Not financial advice. Verify current DW data from the warrant card before
> trading.

## Key principles

### 1. Trade on EFFECTIVE gearing, not simple gearing

```
effective gearing = simple gearing × delta
```

This is the real multiplier — the % the DW moves for a 1% move in the
underlying. Simple gearing alone (3.5–5.7×) overstates leverage; a
high-gearing DW with low delta barely moves.

### 2. Pick moneyness deliberately via delta

Target roughly **delta 0.20–0.80**:

| Delta range | Character | Trade-off |
|---|---|---|
| > 0.80 (deep ITM) | Tracks stock tightly ("sen ~1") | Effective gearing collapses — you pay mostly intrinsic value for little leverage |
| 0.40–0.60 (mid) | Balanced swing trade | Best leverage-to-tracking ratio for most holds |
| < 0.20 (deep OTM) | Lottery ticket | High stated gearing but tiny delta; theta savages it — avoid |

The trader's "sen ≥ 0.8" buys *tracking* but sacrifices the leverage edge.
Choose consciously based on conviction and holding period.

### 3. Compare expensiveness by IMPLIED VOLATILITY (IV), not price

Two DWs on the same stock: the one with **lower IV is cheaper**. Higher IV
makes the warrant more expensive — you need a bigger underlying move just to
break even.

- On the SET, issuer IV is a **biased (typically inflated)** predictor of
  realized volatility — DWs are structurally priced rich. Holding time is a
  cost; favor lower-IV series and shorter holds.

### 4. Time decay (theta) accelerates near expiry

"Far expiry" is right — the time-value bleed is non-linear and worst in the
final weeks. Never hold a near-expiry DW through a slow grind.

### 5. IV crush around earnings

Issuers mark IV *up* into a known event and *down* right after. A correct
directional call can still **lose** if you bought a pumped-IV DW before the
print. See `/set-earnings` for the full earnings overlay.

### 6. Liquidity / spread

Pick actively-traded series; the market-maker bid-ask spread is a real
per-trade cost on top of IV.

### 7. Tracking sanity check

DW (child) moves ~4 ticks when the stock (mother) moves ~5 — "แม่วิ่ง 5 ช่อง
ลูกได้ 4 ปิ๊บ".

## Series naming

`ISSUER + STOCK + C/P + YYMM + letter`

Example: `CPF13C2611A` = issuer 13, CPF, **C**all, exp 2026-11, series A.
Use **P** (put) when the macro favors downside.

## Output template

```
DW:  <SERIES>
  Delta:          <x>
  Eff. gearing:   <simple gearing × delta>
  IV:             <x%> (vs peers: <higher/lower/similar>)
  Expiry:         <month> (<N weeks out>)
  Liquidity:      <volume/spread>
  Verdict:        <pick / avoid / alternative>
```

## When to use

- "Which DW series should I trade on BTG?"
- "Compare DW choices for DELTA"
- "What delta/gearing should I target?"
- "Is this DW expensive (IV)?"
- "DW naming — what does CPF13C2611A mean?"
