---
name: set-pullback
description: >-
  Find and grade PULLBACKS in uptrending SET names that are about to trigger a
  dip or breakout — the pre-signal watch step. Separates a healthy pullback
  (coiling toward the EMA / under the 20-day high, ready to buy on trigger) from
  a fake breakout / distribution / post-spike fade (avoid). Use when the user
  asks "which names are about to enter", "is this a healthy pullback or a fake
  breakout", "what's ready to trigger", or wants the ready-list read. Part of the
  SET DW Swing system (see also: /set-entry, /set-macro, /set-dw-swing).
---

# SET Pullback & Pre-Signal Radar

The step *before* `/set-entry`. A dip or breakout only triggers on the bar it
fires — but the setup **forms during the pullback that precedes it**. This skill
finds names that are one healthy pullback away from a `dip` or `breakout` signal,
and grades the pullback so you don't buy a *fake* breakout or a spike that's
being distributed.

> Not financial advice. All levels are examples; re-derive from live data.

## Mechanical layer — the ready-list

`scan_ready.py` pre-qualifies the SET100 on yesterday's closed data into three
buckets (see `/set-dw-swing`). Run it, then apply the pullback-quality read below.

```
/Users/klang/.venvs/trading-dr/bin/python3 scan_ready.py --no-line        # Q1-Q2 leaders
/Users/klang/.venvs/trading-dr/bin/python3 scan_ready.py --no-line --all-quintiles
```

| Bucket | Meaning | What it still needs |
|---|---|---|
| **DIP READY** | uptrend + touched EMA + RSI/ADX OK | green bar + volume |
| **BRK READY** | uptrend + close within 2% of 20-day high | close > high + volume |
| **ALMOST** | uptrend but one filter short (RSI/ADX/proximity) | momentum to recover |

The scanner tells you *where price is*. It does **not** tell you whether the
pullback is healthy — that's the discretionary read that follows, and it's what
keeps you out of `แลบหลอก`.

## The core question: healthy pullback or distribution?

A stock in an uptrend that is pulling back is EITHER coiling for the next leg
(buy on trigger) OR being distributed / faking a breakout (avoid). Same location
on the chart, opposite outcome. Grade every candidate:

### ✅ HEALTHY pullback — setup forming (watch for trigger)

- **Trend intact:** above EMA20, EMA20 rising, above SMA200.
- **Pulling back TOWARD the EMA/base**, not accelerating away from it.
- **Volume DECLINING into the pullback** — the single most important tell. No
  one is dumping; sellers are just taking short profits (`ย่อแล้ว volume หด`).
- **Orderly bars:** small ranges, no wide red bar that closes on its low.
- **RSI cooling but holding** (≈ 50–65) — momentum resets, doesn't collapse.
- **Prior swing-low structure unbroken.**
- **Breakout coil:** sits just under the 20-day high on quiet volume, no red
  rejection wick.
- → **Action:** put on the watch-list; wait for the confirming green bar + volume
  (dip) or the close above the high + volume (breakout). Then hand to `/set-entry`.

### ❌ FAKE breakout / distribution — avoid (`แลบหลอก`)

- **Poke above resistance that closes red**, especially the same day.
- **Heavy volume DOWN bar** (≥ ~1.5–2×) — that's supply, not a pullback.
- **Wide-range red bar closing at/near the low** = sellers in control.
- **RSI fails below 55 / price loses the EMA** on the pullback.
- **Break of the prior swing low** on volume = structure gone.
- → **Action:** stand aside. A failed breakout usually retests the base, not the
  high. Re-qualify only after it rebuilds above the EMA.

### ⚠️ POST-SPIKE fade — avoid until it re-bases

- **Event/news spike** (+20–30% in 1–2 bars) **then an immediate reversal bar**
  distributing the move.
- **Volume drying up** in the grind that follows = no follow-through demand.
- The spike high becomes heavy overhead supply — don't target it.
- → **Action:** wait for price to fall back to the *pre-spike* base and build a
  fresh setup there, or reclaim the EMA and hold for 2+ bars with RSI > 55.

## Grading rubric (recent worked examples)

| Name | Pullback read | Volume tell | Verdict |
|---|---|---|---|
| JMART | 5 orderly red bars, RSI 71→60, coiling to a rising EMA | vol 0.5–0.9× (drying) | **HEALTHY** → watch for dip trigger |
| VGI | broke 1.07 then −7.5% same day, closed on low | vol 2.0× RED | **FAKE breakout** → avoid |
| MRDIYT | +30% spike then −18% reversal next bar, grind down | vol 9× spike → 0.2× | **POST-SPIKE fade** → avoid |

## Output template

```
READY-LIST (scan_ready.py): <n dip / n brk / n almost>, market breadth <x/y up>

<TICKER> (<sector>, Q<quintile>) — <HEALTHY | FAKE | FADE>
  Trend:    above EMA20 <lvl> (rising?), above SMA200 <lvl>
  Pullback: <toward EMA / coiling under high>, <n> bars, RSI <hi→now>, ADX <x>
  Volume:   <declining / heavy-down / drying> — <healthy tell / supply tell>
  Trigger:  DIP → green bar + vol at <ema/base> │ BRK → close > <20d high> + vol
  Distance: <x%> from EMA, <y%> from 20d high  (how far to a trigger)
  Verdict:  <watch & buy on trigger → /set-entry │ avoid → why>
```

## When to use

- "ตัวไหนกำลังจะเข้า dip/breakout" — which names are about to trigger
- "ย่อนี้สวยไหม หรือแลบหลอก" — healthy pullback or fake breakout?
- "อะไรพร้อมเข้าพรุ่งนี้" — morning ready-list read
- "หุ้นเด้ง +30% เมื่อวาน เข้าได้ไหม" — is this post-spike name buyable?
- Pre-filter a watch-list down to names that hand cleanly to `/set-entry`.
