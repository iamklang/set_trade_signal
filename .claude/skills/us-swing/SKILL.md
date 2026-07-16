---
name: us-swing
description: >-
  Master index for the US (S&P 500) swing trading system — the SET DW Swing
  method ported to US equities. Routes to the right sub-skill. Use when the user
  asks a broad US swing question that spans multiple areas, or wants the full
  workflow end-to-end. For focused questions, prefer the specific sub-skill.
---

# US S&P 500 Swing Trading System — Master Index

The same mechanical swing edge as the SET DW Swing system (`/set-dw-swing`),
re-pointed at the **S&P 500** universe: EMA20 dip / 20-day breakout entry,
composite momentum+trend leader ranking, let-winners-run exits, capital-aware
board-lot sizing, and a daily analytical-brief flow.

> Not financial advice — a structured checklist. All levels are examples;
> re-derive from live data. **The edge was tuned/backtested on the SET, NOT
> re-validated on US equities** — treat US as out-of-sample until it earns its
> own track record (see `/us-evidence`).

## Sub-skills (use directly for focused questions)

| Skill | Covers | Trigger examples |
|---|---|---|
| `/us-macro` | Fed/rates regime, SPX/NDX trend, sector leadership | "market recap", "which sector leads", "rate impact" |
| `/us-entry` | Per-stock chart plan, entry rules, signals | "should I buy NVDA", "entry/stop/target" |
| `/us-earnings` | Earnings overlay: beat/miss, guidance, IV crush | "earnings season", "post-print", "guidance cut" |
| `/us-options` | Options selection (the US analog of a DW) | "which call", "delta/DTE", "IV rank" |
| `/us-risk` | Sizing, exits, lifecycle, cap, rotation, PDT | "how much to buy", "exit rules", "R-multiple" |
| `/us-evidence` | What's validated (and what's NOT) on US | "does it work here", "what's the edge" |

## Core method in one paragraph

Read the **macro driver** first (Fed path → real yields → risk-on/off, which
sectors win), confirm the **index regime** with the Daily **20-EMA** on SPX/NDX,
find **who is leading** (sector + mega-cap breadth), then for each candidate:
mark the EMA + base + resistance, **buy on the dip** to support (with a
confirming green candle) or on a clean **20-day breakout**, set a **structural
stop** below it, **target +1R then let it run** (trail the 20-EMA, no cap), and
express it either in the **stock** or a **well-specced option/LEAPS**. Never
chase into resistance. Execute as a **patient limit trader on liquid names**.

## Daily automation (US market hours, ET)

| Time (ET) | Script | What it does |
|---|---|---|
| ~08:45 | `./us_morning` | Pre-open ready list → analytical brief (DIP/BRK ready) |
| ~16:15 | `./us_daily` | EOD pipeline: dip scan + composite rank + bull scan |
| ~16:30 | `alert.py` (US profile) | EOD analytical brief (events / health / action) |

The US flow reuses the SET scripts under a **market profile** (`TR_MARKET=us`):
same code, separate state (`us/positions.json`, `us/quarter.json`, `us/scans/`).

## Python scanner & tooling (shared with SET, US profile)

| Script | Purpose |
|---|---|
| `scan_dip.py --market us` | BUY(dip/brk) scanner + us/positions.json writer |
| `scan_ready.py --market us` | Morning ready-list analytical brief |
| `scan_bull.py --market us` | Broad bullish scan |
| `alert.py --market us` | EOD analytical brief |
| `quarterly_review.py --market us` | Q-Close analytical review |
| `positions.py` | Stateful lifecycle engine (let-winners-run) |
| `setdw_signal.py` | Signal logic: buy_signal, trade_plan, size tilt |
| `composite.py` | Multi-factor ranking (momentum + trend) |
| `costs.py` (us mode) | US cost model (~$0 commission + penny half-spread) |

## What changes vs the SET system

| Dimension | SET | US (S&P 500) |
|---|---|---|
| Universe | SET100 | S&P 500 (`us500.txt`) |
| Instrument | DW (derivative warrant) | Stock, or listed **option/LEAPS** |
| Board lot | 100 shares | **1 share** |
| Costs | tick-spread + 0.157% comm | ~$0 comm + penny half-spread |
| Macro driver | oil, baht, foreign flow (NVDR) | Fed path, real yields, VIX, mega-cap breadth |
| Leverage trap | DW IV / theta | option IV rank / theta / DTE; PDT rule |
| Currency | THB | USD |

## Sources & honesty

The mechanical core (dip/breakout + composite + let-run + quintile sizing) is
the SET-validated method. **On US it is unproven** — sector drivers, earnings
read-throughs, cost assumptions, and even the 20-EMA edge must be re-checked on
US data before sizing up. Start small, log everything, review by quarter.
