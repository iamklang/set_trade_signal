---
name: set-dw-swing
description: >-
  Master index for the SET DW Swing trading system — routes to the right
  sub-skill. Use when the user asks a broad SET trading question that spans
  multiple areas, or wants the full workflow end-to-end. For focused questions,
  prefer the specific sub-skill directly.
---

# SET DW Swing Trading System — Master Index

A repeatable swing-trading workflow for SET stocks and derivative warrants
(DWs), distilled from the **DW Trader** livestream method and validated with
backtests on SET100.

> Not financial advice — a structured checklist. All levels are examples;
> re-derive from live data.

## Sub-skills (use directly for focused questions)

| Skill | Covers | Trigger examples |
|---|---|---|
| `/set-macro` | Macro regime, index trend, sector leadership | "ใครแบก", "SET recap", "oil impact" |
| `/set-entry` | Per-stock chart plan, entry rules, signals | "should I buy X", "entry/stop/target" |
| `/set-earnings` | Earnings overlay: งบ, sell-on-fact, SC, IV crush | "งบ season", "SC play", "pre-print" |
| `/set-dw` | DW selection: delta, gearing, IV, expiry | "which DW series", "compare DWs" |
| `/set-risk` | Sizing, exits, lifecycle, cap, rotation | "how much to buy", "exit rules", "R-multiple" |
| `/set-evidence` | Backtest results, research, limitations | "does it work", "what's the edge" |

## Core method in one paragraph

Read the **macro driver** first (geopolitics → oil → which sectors win), confirm
the **index regime** with the Daily **20-EMA**, find **who is carrying the
market** (sector leadership), then for each candidate: mark the EMA + base +
resistance, **buy on the dip** to support (with a confirming green candle), set
a **structural stop** below it, **target +1R then let it run**, and execute
through a **well-specced DW** (liquid, mid-delta, lower IV, far expiry). Never
chase into resistance. Execute as a **patient limit trader on liquid names**.

## Daily automation

| Time | Script | What it does |
|---|---|---|
| 08:30 | `./morning_scan` | Pre-market ready list → LINE (DIP/BRK READY + holdings + sells) |
| 17:00 | `./daily_scan` | EOD pipeline: scan_dip + scan_bull + NVDR + git snapshot |
| 17:30 | `alert.py` | BUY(dip) alert → LINE (signals + managed watchlist + capital) |

## TradingView scripts (Pine v6)

Two companion scripts in the project root:

- **`set-dw-swing.pine`** — live indicator (add to any SET stock or DW chart).
- **`set-dw-swing-strategy.pine`** — backtest version (run on a SET stock, Daily).

| On the chart | Means |
|---|---|
| 🟢 **BUY** (green) | Dip-to-EMA confirmed; shows Entry/Stop/TP |
| ⚠ **BUY** (orange) | Same, but within IV-crush window (earnings) |
| 🔴 **SELL** (red) | Exit — trend broke or rejection at resistance |
| Green/red candles | Uptrend (buy dips) / downtrend (bounce only) |
| **ACTION** box | One-glance state: BUY / SELL / HOLD / STAND ASIDE |

## Python scanner & tooling

| Script | Purpose |
|---|---|
| `scan_dip.py` | BUY(dip/brk) scanner + positions.json writer |
| `scan_bull.py` | Broad bullish scan (trend/breakout/reclaim/golden/dip) |
| `scan_ready.py` | Morning ready-list (one bar away from triggering) |
| `alert.py` | Watchlist BUY(dip) alert + LINE notification |
| `positions.py` | Stateful lifecycle engine (let-winners-run) |
| `setdw_signal.py` | Signal logic: buy_signal, trade_plan, size tilt |
| `profiles.py` | Per-stock overrides (RSI/ADX thresholds) |
| `costs.py` | SET cost model (tick-based spread + commission) |
| `set_data.py` | Data: SET official (Playwright) or Yahoo Finance |
| `composite.py` | Multi-factor ranking (momentum + trend) |
| `line_notify.py` | LINE Messaging API push notifications |
| `trade_dashboard.py` | Web dashboard: signals, holdings, plan vs actual |
| `quarterly_review.py` | Quarter-end review: expectancy, PF, max DD |
| `collect_nvdr.py` | NVDR (foreign flow) daily data collection |
| `trade_log.py` | Manual execution ledger (plan vs actual) |

## Claude Code agents

| Agent | When |
|---|---|
| `morning-ready` | Pre-market readiness check (ก่อน SET เปิด) |
| `eod-monitor` | End-of-day monitoring (หลัง SET ปิด) |
| `quarter-review` | Quarterly review (สิ้นไตรมาส) |

## Sources

**Primary method:** YouTube livestreams by **DW Trader** (`#Liveล่าหุ้น`).
**Expert grounding:** verified deep-research pass (24 sources, 25 claims
fact-checked) — SET DW intro, warrants.com.hk, IFEC, Tharavanij 2015,
Fifield 2008, Park & Irwin 2004, ScienceDirect, ipresage.
