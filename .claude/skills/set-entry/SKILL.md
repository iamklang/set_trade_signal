---
name: set-entry
description: >-
  Per-stock chart plan and entry rules for SET swing trading — mark EMA/base/
  resistance, buy-on-dip vs breakout, confirming candle, structural stop,
  R-targets. Use when the user asks "should I buy X here", wants entry/stop/
  target for a specific name, or needs a chart plan. Part of the SET DW Swing
  system (see also: /set-macro, /set-earnings, /set-dw, /set-risk).
---

# SET Chart Plan & Entry Rules

Per-stock workflow from the **DW Trader** method. For each candidate, build a
chart plan on the Daily, then decide entry.

> Not financial advice. All levels are examples; re-derive from live charts.

## Chart plan (Daily chart)

For each candidate, mark:

1. **Orange 20-EMA** — dynamic support in uptrend / bounce target in downtrend.
2. **Base / support zone** (where price last based — "ฐาน").
3. **Resistance / breakout level.**
4. **Confluence:**
   - Master Bar (wide high-volume candle marking a defended zone)
   - Volume spikes, declining volume into a pullback (healthy)
   - Heavy sell volume that *fails to push price down* (possible accumulation)
5. **200-day line** as a deeper structural backstop alongside the 20-EMA.
6. **Open gaps** — mark as targets/resistance; a gap-up that holds/twists
   (`บิดยัน`) after good งบ is confirmation.
7. **Multi-bottom bases** (double / triple bottom) as high-conviction support.

Drop to the **60-min** chart for finer entry timing.

### Watch for traps

- **Fake breakout (`แลบหลอก`):** a poke above resistance that closes red = do
  not chase.
- **Pre-earnings shake-out:** recovery names often get knocked down just before
  a known report date, then jump if งบ is OK — treat that dip into support as
  an entry, not a breakdown.
- **Volume around the print:** require declining volume into the pre-print base;
  require rising/peak volume to confirm a post-print breakout; a high-volume
  down-bar that *holds* support = accumulation.

## Entry rules

- **Trade with the trend, never against the global main trend.**
- **Buy on the dip** to the EMA/base zone — don't chase. "Chasing = getting
  stuck at the top (ดอย)."
- **Wait for a confirming green candle** at support before entering; buying
  before the bounce confirms is gambling (วัดดวง).
- **Breakout entries** only if you accept a tight stop at the breakout level.

### Mechanical signals (from the Python scanner)

| Signal | Condition |
|---|---|
| `dip` | Pullback to EMA20 in uptrend + green bar + RSI≥55 + ADX≥20 + volume |
| `breakout` | Break 20-day high in uptrend + volume |

Live default = `dip_or_brk` — either signal triggers.

## Output template

```
<TICKER> (<sector>) — <call/put> bias
  Trend:    Daily candle <above/below> orange 20-EMA (<level>)
  Setup:    <buy-on-dip | breakout | Selling-Climax | pre-position>
  Buy zone: <support/base> ; confirm green candle
  Stop:     <structural level>  (1R = entry − stop)
  Target:   <EMA or resistance band>  (≥2R?)
  Size:     <(equity × 1%) ÷ (entry − stop)> ; round to 100 shares
  Note:     <volume/Master Bar/gap; IV-crush risk if pre-earnings>
```

## When to use

- "Should I buy DELTA / CPF / GULF here?"
- "Entry, stop, target for KCE"
- "Chart plan for BGRIM"
- "Is this a fake breakout or real?"
