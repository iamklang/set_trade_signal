---
name: us-entry
description: >-
  Per-stock chart plan and entry rules for US (S&P 500) swing trading — mark
  EMA/base/resistance, buy-on-dip vs 20-day breakout, confirming candle,
  structural stop, R-targets. Use when the user asks "should I buy X here",
  wants entry/stop/target for a specific name, or needs a chart plan. Part of
  the US swing system (see also: /us-macro, /us-earnings, /us-options, /us-risk).
---

# US Chart Plan & Entry Rules

Per-stock workflow (SET method ported to US). For each candidate, build a chart
plan on the Daily, then decide entry.

> Not financial advice. All levels are examples; re-derive from live charts.

## Chart plan (Daily chart)

For each candidate, mark:

1. **20-EMA** — dynamic support in uptrend / bounce target in downtrend.
2. **Base / support zone** (where price last based).
3. **Resistance / breakout level** (prior swing high, round numbers, gap edges).
4. **Confluence:**
   - High-volume "master bar" marking a defended zone
   - Volume spikes; declining volume into a pullback (healthy)
   - Heavy sell volume that *fails to push price down* (accumulation)
   - VWAP / anchored-VWAP from the last major pivot (US intraday tell)
5. **50-DMA & 200-DMA** as deeper structural support and the trend backstop.
6. **Open gaps** — mark as targets/resistance; a gap-up that holds after good
   earnings is confirmation.
7. **Multi-bottom bases** (double/triple bottom) as high-conviction support.

Drop to the **hourly / 15-min** for finer entry timing.

### Watch for traps

- **Fake breakout:** a poke above resistance that closes back below = don't chase.
- **Pre-earnings shake-out:** names get knocked down before a known report date,
  then jump if the print is OK — treat the dip into support as an entry, not a
  breakdown (but respect the print-day risk rule, see `/us-earnings`).
- **Volume around the print:** declining volume into the pre-print base; rising/
  peak volume to confirm a post-print breakout; a high-volume down-bar that
  *holds* support = accumulation.

## Entry rules

- **Trade with the trend, never against the primary (200-DMA) trend.**
- **Buy on the dip** to the EMA/base zone — don't chase.
- **Wait for a confirming green candle** at support before entering; buying
  before the bounce confirms is gambling.
- **Breakout entries** only if you accept a tight stop at the breakout level.

### Mechanical signals (from the Python scanner)

| Signal | Condition |
|---|---|
| `dip` | Pullback to EMA20 in uptrend + green bar + RSI≥55 + ADX≥20 + volume |
| `breakout` | Break 20-day high in uptrend + volume |

Live default = `dip_or_brk` — either signal triggers. Same thresholds as SET
(re-tune on US data before trusting; see `/us-evidence`).

## Output template

```
<TICKER> (<sector>) — long/short bias
  Trend:    Daily candle <above/below> 20-EMA (<level>); vs 200-DMA <above/below>
  Setup:    <buy-on-dip | breakout | post-earnings-follow | pre-position>
  Buy zone: <support/base> ; confirm green candle
  Stop:     <structural level>  (1R = entry − stop)
  Target:   <EMA or resistance band>  (≥2R?)
  Size:     <(equity × 1%) ÷ (entry − stop)> shares (US lot = 1)
  Note:     <volume/gap/VWAP; earnings date + IV-crush risk if pre-print>
```

## When to use

- "Should I buy NVDA / AAPL / GOOGL here?"
- "Entry, stop, target for AMD"
- "Chart plan for META"
- "Is this a fake breakout or real?"
