---
name: us-risk
description: >-
  Risk management, position sizing, and exit rules for the US (S&P 500) swing
  system — fixed-fractional sizing (1-share lot), R-multiples, let-winners-run
  lifecycle (breakeven at T1, trail EMA after, no cap), position cap, composite-
  quintile tilt, rotation, cooldown, and the US-specific PDT rule. Use when the
  user asks about sizing, stops, exits, position management, or "how much to
  buy". Part of the US swing system (see also: /us-entry, /us-macro, /us-options).
---

# US Risk Management & Position Lifecycle

The exit and sizing rules from the SET system, applied to US equities. How you
size and exit matters more than the entry signal.

> Not financial advice. The edge is thin and right-tailed — many small losers, a
> few big winners. **Unproven on US** — start small (see `/us-evidence`).

## Position sizing

### Fixed-fractional risk sizing

Risk a fixed **~1% (max 2%)** of equity per trade. Back into size from the stop:

```
shares = (equity × risk%) ÷ (entry − stop)
```

- US **board lot = 1 share** (no 100-share rounding; fractional shares optional).
- Cap at `equity ÷ entry` (can't buy more than capital allows).
- Size from **available capital** (equity − committed), not total equity — but
  keep the RISK budget on full equity so wide-stop names still clear a position
  (same fix as the SET book: risk off equity, affordability cap off available).
- With **options**, 1R = premium-at-risk; size contracts so a full loss ≈ 1%.

### Composite-quintile tilt

Scale size by composite ranking (momentum + trend):

| Quintile | Multiplier |
|---|---|
| Q1 (top leaders) | 1.5× |
| Q2 | 1.25× |
| Q3 | 1.0× |
| Q4 | 0.75× |
| Q5 | 0.5× |

(Validated on SET; re-check the tilt on US before trusting the magnitudes.)

### Exposure overlay

`position size × voltgt × ddbrake` — voltgt trims when index vol runs hot;
ddbrake halves new sizing when the book is >12% off its equity peak.

## R-multiples

**1R = your stop distance.** Judge every trade by reward-to-risk *before* entry —
take setups offering **≥ 2R–3R**. Track outcomes in R so expectancy
`(avg win × win%) − (avg loss × loss%)` stays positive over many trades.

## Position lifecycle (let-winners-run)

```
BUY(dip/brk)      close >= T1 (+1R)                 close < EMA20 or stop
  │ enter FULL      │ stop → breakeven, let run       │ exit
  ▼                 ▼                                 ▼
HOLDING/FULL ────▶ HOLDING/RUN ──────────────────▶ SELL_FLAGGED → dropped
  └─ close <= stop ─────────────────────────────▶ SELL_FLAGGED → dropped
```

- **FULL** (before T1): exit ONLY on the structural stop. Do NOT exit on
  close < EMA — that rule cut too many trades early and made the book a net loser.
- **At +1R (T1)**: move stop to breakeven. Now it can't lose money.
- **RUN** (after T1): **no take-profit cap** — let it run until it loses the
  20-EMA or the (breakeven) stop.
- **Trailing exit**: close < EMA20 (only after T1) or close ≤ stop.

### Sell reasons: STOP (full loss) · BE (scratch) · TRAIL (take profit) · ROTATE (replaced)

## Position cap & rotation

- **Cap ~12 concurrent names.** When full, a weaker new hit is skipped; a stronger
  new hit rotates out the weakest incumbent (composite / upside-to-T1).
- **Cooldown: 5 sessions** after a full exit before the same name re-enters.

## US-specific rules

- **PDT (Pattern Day Trader):** with a margin account under **$25,000**, you're
  limited to **3 day-trades per rolling 5 sessions**. This is a swing system
  (multi-day holds), so it mostly avoids PDT — but closing a same-day entry counts.
  Under $25k, use a **cash account** (no PDT, but T+1 settlement limits reuse of
  funds) or keep holds overnight.
- **Options assignment / expiry:** manage ITM options before expiry; don't get
  assigned by accident. Never hold a short-dated option through theta cliff.
- **Overnight/gap risk:** US single-stock gaps are large; the stop is a *trigger*,
  not a guaranteed fill — size for slippage on gap-throughs.
- **Wash-sale rule:** re-entering a loss within 30 days disallows the tax loss;
  the 5-session cooldown mostly sidesteps intent but track it for taxes.

## Capital discipline

- Don't tie capital up in a chased position and miss better setups.
- **Tranche in:** a first lot at the base, a 2nd at deeper support — not one
  all-in buy. Never average down a loser that broke its stop.
- **Hedge by switching sides** (or buying index puts) if the macro flips.

## When to use

- "How much to buy? What size?"
- "Exit rules — when do I sell?"
- "Does the PDT rule apply to me?"
- "Book is full — should I rotate?"
