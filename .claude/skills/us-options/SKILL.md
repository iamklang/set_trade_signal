---
name: us-options
description: >-
  Options selection for US (S&P 500) swing trading — the US analog of picking a
  DW: delta/moneyness, effective leverage, implied volatility (IV rank), theta,
  DTE/expiry, IV crush, LEAPS. Use when the user wants to express a swing view
  with options, pick a strike/expiry, or understand options mechanics. Part of
  the US swing system (see also: /us-entry, /us-earnings, /us-risk).
---

# US Options Selection (the DW analog)

The SET system traded **DWs** for leverage; the US analog is a **listed option**
(or LEAPS). Same idea — a well-specced leverage instrument on a liquid leader —
but you control strike, expiry, and structure directly.

> Not financial advice. Verify the live option chain (delta, IV, spread, OI)
> before trading. Options can go to zero; size as premium-at-risk.

## Key principles

### 1. Trade on EFFECTIVE leverage, not notional

```
effective leverage ≈ (delta × underlying price) / option price
```

This is the real multiplier — how much the position moves for a 1% move in the
stock. A cheap far-OTM call has high stated leverage but tiny delta and brutal
theta; it barely tracks.

### 2. Pick moneyness deliberately via delta

Target roughly **delta 0.50–0.80** for a directional swing:

| Delta | Character | Trade-off |
|---|---|---|
| > 0.80 (deep ITM) | Tracks the stock ~1:1 | Less leverage, more capital, low theta — closest to owning stock with a defined stop |
| 0.50–0.70 (ATM-ish) | Balanced swing | Good leverage-to-tracking; standard directional pick |
| < 0.30 (OTM) | Lottery ticket | High stated leverage, tiny delta, theta savages it — avoid for swings |

For a multi-week swing, **ITM/ATM (0.6–0.8 delta)** tracks the chart plan best.

### 3. Compare expensiveness by IV RANK, not price

- **IV rank / percentile** tells you if premium is cheap or rich vs the stock's
  own history. Buying options when IV rank is **high** means you overpay and need
  a bigger move to break even.
- Prefer to **buy premium when IV rank is low**; when IV is high, prefer stock,
  spreads (sell some premium), or wait.

### 4. Theta accelerates near expiry — pick enough DTE

- For a ~20-day swing (the system's hold), use **45–90 DTE** so time decay is
  slow during the hold; never swing a weekly (7 DTE) — theta will eat you even if
  you're right.
- **LEAPS (6–24 months, deep ITM ~0.8 delta)** are the cleanest "stock with
  leverage and a defined max loss" for a longer trend hold.

### 5. IV crush around earnings

IV is bid up into a print and collapses after. A correct directional call can
still lose if you bought pumped IV pre-print. Prefer entering **after** the print,
or express pre-print in stock / longer-dated options. See `/us-earnings`.

### 6. Liquidity / spread

Trade only **liquid chains**: tight bid-ask (penny-wide on liquid names), high
open interest, real volume. The spread is a per-trade cost on top of IV — wide
chains quietly kill the edge (the US analog of a thin DW).

### 7. Defined-risk structures

- **Long call/put** — simplest directional; max loss = premium.
- **Vertical debit spread** — cheaper, caps upside, cuts IV/theta sensitivity;
  good when IV rank is elevated.
- **LEAPS** — stock replacement for trend holds.

## Position sizing with options

Size by **premium-at-risk = your 1R**, not notional. If the thesis stop is hit on
the *stock*, exit the option — don't let a defined-risk long lull you into holding
to zero. See `/us-risk`.

## Output template

```
OPTION:  <TICKER> <exp> <strike> C/P
  Delta:          <x>
  Eff. leverage:  <(delta × spot) / premium>
  IV rank:        <x%>  (cheap / rich vs its history)
  DTE:            <n days>  (45–90 for a swing)
  Liquidity:      <spread / OI / vol>
  Premium (1R):   <$ at risk = 1R>
  Verdict:        <pick / avoid / use stock or spread instead>
```

## When to use

- "Which call should I buy on NVDA for a swing?"
- "What delta/DTE should I target?"
- "Is this option's IV too rich?"
- "Stock, call, spread, or LEAPS for this trade?"
