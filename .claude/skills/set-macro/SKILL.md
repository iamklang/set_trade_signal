---
name: set-macro
description: >-
  Top-down macro reading for SET swing trading — geopolitics/oil/NDX regime,
  index trend (Daily 20-EMA), and sector leadership ("ใครแบก"). Use when the
  user wants a weekly/daily SET recap, sector rotation view, or "who is
  carrying the index" analysis. Part of the SET DW Swing system (see also:
  /set-entry, /set-earnings, /set-dw, /set-risk, /set-evidence).
---

# SET Macro & Sector Reading

Top-down workflow from the **DW Trader** method. Read the macro first, then
the index, then find who's carrying.

> Not financial advice — a structured checklist. All levels are examples;
> re-derive from live data.

## 1. Read the macro driver

- **Geopolitics / risk events:** war vs. peace (Mideast, Hormuz), central-bank
  meetings (Fed/ECB/BoT — MPC/กนง.), key data (PCE, GDP, Thai exports), index
  rebalances (FTSE, SET50 in/out).
- **Oil (NYMEX/Brent):** the pivotal driver.
  - **Oil falling** → bullish anti-commodity/petrochem, power/utilities,
    airlines, tourism, retail, livestock; bearish oil E&P.
  - **Oil rising** → reverse.
- **Global tech (Nasdaq/NDX, TSMC/Samsung):** when NDX is near highs, flow
  rotates back into Thai chips first ("when in doubt, money rotates back to
  chips").
- Decide the **regime**: *peace / oil-down* vs *war / oil-up*. This sets sector
  direction and whether you favor **call** or **put** DWs on each name.

## 2. Check the index regime (SET + S50 futures)

- Is price **above or below the Daily 20-EMA** (the "orange line")?
  - **Above → uptrend** → buy dips toward the EMA/support.
  - **Below → downtrend** → only play bounces; sell into the EMA.
- Define the **week's range**: support band, resistance band, deeper
  "head-break" floor. State a plain range call (e.g. "SET 1558–1610 this
  week").

## 3. Identify "who is carrying" (ใครแบก) — sector leadership

Bucket the market and note leaders vs. laggards:

| Bucket | Tickers (examples) | Logic |
|---|---|---|
| Oil / E&P | PTTEP, IRPC, IVL | War/supply; play both call & put on news |
| Petrochem / anti-commodity | IVL, PTTGC, SCC, SCGP, TOA | Benefit from falling oil (input cost) |
| Semiconductor / chips | DELTA, CCET, HANA, KCE | Track NDX/global chips; buy on dip |
| Banks | KTB, KBANK, KKP | Rate narrative; strong leaders = index floor |
| Power / utilities | GPSC, BGRIM, GULF | Lower fuel cost; GULF also AI/data-center |
| Construction | STECON, CK | Government stimulus, infrastructure |
| Tourism / airport / hospital / retail | AOT, MINT, BH, BDMS, CRC, CPALL | Peace → more tourism |
| Livestock (หมูไก่) | BTG, CPF, TFG | Cycle turn + lower logistics cost |

**Candidate** = a leader currently **dipping** to support, **or** a cheap
laggard with a clear catch-up story and "room left" (อัพไซด์ยังเหลือ). Use
banks as a *tell*: when banks are strong, the index is hard to push down.

## Output template

```
MACRO: <regime> — oil <up/down>, NDX <near highs/weak>, key events <…>
INDEX: SET <px> vs 20-EMA <above/below>; week range <low>–<high>
LEADERS: <sectors carrying> | LAGGARDS w/ room: <…>
```

## When to use

- "Do a SET recap / who's carrying the index this week?"
- "SET above or below trend? Range this week?"
- "Oil is down — which sectors benefit?"
- "Macro driver for the week?"
