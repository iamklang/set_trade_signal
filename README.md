# SET DW Swing Trading System

ระบบสแกนและจัดการพอร์ต swing-trade สำหรับหุ้น SET100 — ใช้ EMA20 pullback (dip) และ breakout เป็นสัญญาณเข้า พร้อม composite ranking (momentum + trend) ปรับขนาดโพซิชัน

## Quick Start

```bash
# venv
~/.venvs/trading-dr/bin/python

# EOD pipeline (รันหลังตลาดปิด ~17:00)
./daily_scan

# สแกนด้วยมือ
~/.venvs/trading-dr/bin/python scan_dip.py --composite --equity 100000

# ดูหน้า dashboard
~/.venvs/trading-dr/bin/python trade_dashboard.py
# -> http://localhost:8060
```

## Config

| File | หน้าที่ |
|---|---|
| `quarter.json` | ตั้งค่าประจำไตรมาส: equity, risk%, max positions, max drawdown |
| `market_regime.json` | สถานะ exposure overlay (voltgt × ddbrake) — อัพเดตอัตโนมัติทุกรอบสแกน |
| `positions.json` | สถานะหุ้นที่ถืออยู่ (HOLDING/SELL_FLAGGED) — เขียนโดย `scan_dip.py` เท่านั้น |
| `composite_rank.csv` | อันดับ composite quintile ของ SET100 |
| `watchlist.txt` | รายชื่อหุ้นสำหรับ alert.py |
| `set100.bk.txt` | รายชื่อ SET100 universe |

## Core Scripts

### สแกนรายวัน

| Script | หน้าที่ | ตัวอย่าง |
|---|---|---|
| `daily_scan` | EOD pipeline รวม: scan_dip → scan_bull → collect_nvdr → git commit | `./daily_scan` |
| `scan_dip.py` | สแกน BUY(dip\|breakout) + จัดการ positions.json | `python scan_dip.py --composite --equity 100000 --asof 2026-07-13` |
| `scan_bull.py` | สแกนสัญญาณ bullish กว้าง (trend/breakout/reclaim/golden/dip) | `python scan_bull.py --no-line --leaders-only` |
| `scan_ready.py` | Pre-market ready-list: หุ้นที่ใกล้จะ trigger (DIP READY/BRK READY) | `python scan_ready.py` |

### แจ้งเตือน & Dashboard

| Script | หน้าที่ | ตัวอย่าง |
|---|---|---|
| `alert.py` | แจ้งเตือน BUY(dip) ผ่าน LINE + macOS notification | `python alert.py --no-line --leaders-only` |
| `trade_dashboard.py` | Web dashboard: สัญญาณ, หุ้นที่ถือ, plan vs actual, quarterly review | `python trade_dashboard.py` |

### Review & Data

| Script | หน้าที่ | ตัวอย่าง |
|---|---|---|
| `quarterly_review.py` | สรุปไตรมาส: expectancy, profit factor, signal attribution, max DD | `python quarterly_review.py --quarter 2026Q3` |
| `collect_nvdr.py` | ดึงข้อมูล NVDR (foreign flow) รายวัน | `python collect_nvdr.py` |
| `validate_scans.py` | ตรวจสอบ dip_scan CSV กับข้อมูลจริง | `python validate_scans.py` |

## Backtests

| Script | ทดสอบอะไร |
|---|---|
| `bt_portfolio.py` | Portfolio-level: sizing, cap sweep, cost models |
| `bt_exits.py` | เปรียบเทียบ exit rules (V1-V5) |
| `bt_composite.py` | Walk-forward quintile test ของ composite ranking |
| `bt_weekly.py` | 1-week horizon: V5 vs weekly variants |
| `bt_triggers.py` | เปรียบเทียบ bull-scan triggers vs strict BUY(dip) |
| `bt_holdout.py` | Time-split holdout: composite weight overfitting check |
| `bt_quality.py` | ROE quality factor improvement test |

## Entry Signals

Live default = `--entry dip_or_brk_or_cdc` — เข้าซื้อเมื่อ **ตัวใดตัวหนึ่ง** เข้าเงื่อนไข:

| Signal | เงื่อนไข |
|---|---|
| `dip` | Pullback ลงมาที่ EMA20 ในเทรนด์ขาขึ้น + green bar + RSI≥55 + ADX≥20 + volume |
| `breakout` | เบรก high 20 วัน ในเทรนด์ขาขึ้น + volume |
| `cdc` | **CDC ActionZone (HAP)** — แท่งแรกที่เข้าโซนเขียว (EMA12>EMA26 & close>EMA12) = วันแรกที่เทรนด์กลับเป็นขาขึ้น |

โหมดอื่น: `--entry dip` (dip อย่างเดียว), `--entry dip_or_brk` (dip หรือ breakout)

## Position Lifecycle

```
BUY(dip/brk/cdc)  close >= T1 (+1R)                 close < EMA20 or stop
  │ enter FULL      │ stop → breakeven, let run       │ exit
  ▼                 ▼                                 ▼
HOLDING/FULL ────▶ HOLDING/RUN ──────────────────▶ SELL_FLAGGED → dropped
  └─ close <= stop ─────────────────────────────▶ SELL_FLAGGED → dropped
```

- **FULL**: ถือเต็ม ก่อน T1 — ออกเมื่อหลุด stop เท่านั้น
- **RUN**: ล็อกทุนแล้ว ปล่อยวิ่ง — ออกเมื่อหลุด EMA20 หรือ stop (= breakeven)
- **ไม่มี T2 cap** — ปล่อยวิ่งจนหลุด EMA (right tail ดีกว่า cap)

## Sizing & Rotation

- **Capital-aware**: size คำนวณจากทุนที่เหลือ (equity - committed) ไม่ใช่ทุนทั้งหมด
- **Quintile tilt**: Q1 × 1.5, Q2 × 1.25, Q3 × 1.0, Q4 × 0.75, Q5 × 0.5
- **Exposure overlay**: voltgt (target 18% vol) × ddbrake (halve at 12% DD from peak)
- **Smart rotation**: เมื่อ book เต็ม ถ้าตัวใหม่มี upside to T1 ดีกว่าตัวเก่า > 5% จะ auto-flag ขายตัวเก่า
- **Cooldown**: 5 trading sessions หลัง full exit ก่อนเข้าซ้ำ (ป้องกัน whipsaw)
- **Position cap**: max 12 ตำแหน่ง เก็บตัวที่ composite score สูงสุด

## Support Libraries

| Module | หน้าที่ |
|---|---|
| `setdw_signal.py` | Signal logic: buy_signal, trade_plan, size tilt, exposure overlay |
| `bullish_signals.py` | Extended signals: breakout, reclaim, golden cross, trend |
| `positions.py` | Stateful lifecycle engine: update, opportunity_score, capital tracking |
| `composite.py` | Cross-sectional multi-factor ranking (momentum + trend) |
| `costs.py` | SET cost model (tick-based spread + commission) |
| `profiles.py` | Per-stock parameter overrides (RSI/ADX thresholds) |
| `set_data.py` | Data source: SET official (Playwright) or Yahoo Finance |
| `line_notify.py` | LINE Messaging API push notifications |
| `trade_log.py` | Manual execution ledger (plan vs actual) |
| `housekeeping.py` | Log/CSV retention cleanup |

## Tests

```bash
~/.venvs/trading-dr/bin/python -m pytest tests/ -v
```
