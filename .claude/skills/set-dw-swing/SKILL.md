---
name: set-dw-swing
description: >-
  Run a weekly/daily SET (Thai stock) swing-trading recap and watchlist the way
  the "DW Trader" livestream does — top-down macro (war/peace → oil → sector
  rotation), a Daily 20-EMA trend filter, buy-the-dip at support zones, sell into
  resistance/EMA, structural stops, DW (derivative warrant) selection by
  sensitivity/gearing/liquidity/expiry, AND earnings-season stock-picking
  (consensus beat/miss, reported-vs-not, sell-on-fact, Selling-Climax, peer
  read-through, pre-print positioning). Use when the user wants to screen Thai SET
  stocks, build a DW watchlist, decide entries/exits/stops on a name, pick which
  DW series to trade, read "who is carrying the index" sector leadership, or trade
  around quarterly earnings (งบ). Grounded with verified research on DW mechanics
  (effective gearing, delta/moneyness, implied volatility, IV crush, theta), the
  empirical evidence for trend rules on the SET, and fixed-fractional / R-multiple
  risk sizing. Not investment advice — a structured checklist combining one
  trader's method with fact-checked best practice.
---

# SET DW Swing-Trading Recap

A repeatable workflow distilled from the **"DW Trader" / Live ล่าหุ้น** Thai
stock livestream. It trades **DWs (derivative warrants)** on liquid SET stocks,
swing/range style, driven by a top-down macro narrative and one simple technical
filter. Keep it simple — "even a high-schooler should understand it."

> ⚠️ **Not financial advice.** This encodes one trader's discretionary process so
> it can be applied consistently. All levels are examples; always re-derive them
> from live charts. State assumptions and let the user decide.

## Core method in one paragraph

Read the **macro driver** first (geopolitics → oil → which sectors win), confirm
the **index regime** with the Daily **20-EMA "orange line"**, find **who is
carrying the market** (sector leadership), then for each candidate: mark the
EMA + base/support zone + resistance, **buy on the dip** to support (with a
confirming green candle), set a **structural stop** below it, **target the EMA or
next resistance**, and execute through a **well-specced DW** (liquid, sensitivity
≥ ~0.8, gearing ~3.5–5.7×, expiry not imminent). Never chase into resistance.
Execute as a **patient limit trader on liquid names** (place the order at the signal
close, don't cross the spread, skip thin names) — the 2026 cost study found this
worth as much as the signal itself. (The mechanical version of all this — entry,
let-run exit, cap, sizing, cost/liquidity gates — lives in the Python scanner below;
the ★ CORE CONCEPT bullet in "Own backtest" is the one-glance summary of what survived
testing.)

## When to use this skill

- "Do a SET recap / who's carrying the index this week?"
- "Build me a DW watchlist for these sectors."
- "Should I buy DELTA / CPF / GULF here — entry, stop, target?"
- "Which DW series should I trade on BTG?"
- "Is SET above or below its trend? What's the range this week?"

## Step-by-step workflow

### 1. Read the macro driver (top-down)
- **Geopolitics / risk events:** war vs. peace (e.g. Mideast ceasefire, Hormuz),
  central-bank meetings (Fed/ECB/BoT — MPC/กนง.), key data (PCE, GDP, Thai
  exports), index rebalances (FTSE, SET50 in/out).
- **Oil (NYMEX/Brent):** the pivotal driver. **Oil falling** ⇒ bullish
  anti-commodity/petrochem, power/utilities, airlines, tourism, retail, livestock;
  bearish oil E&P. **Oil rising** ⇒ reverse.
- **Global tech (Nasdaq/NDX, TSMC/Samsung):** when NDX is near highs, flow rotates
  back into Thai chips first ("when in doubt, money rotates back to chips").
- Decide the **regime**: *peace / oil-down* vs *war / oil-up*. This sets sector
  direction and whether you favor **call** or **put** DWs on each name.

### 2. Check the index regime (SET + S50 futures)
- Is price **above or below the Daily 20-EMA** (the "orange line")?
  - **Above ⇒ uptrend** → buy dips toward the EMA/support.
  - **Below ⇒ downtrend** → only play bounces; sell into the EMA.
- Define the **week's range**: support band, resistance band, deeper "head-break"
  floor. State a plain range call (e.g. "SET 1558–1610 this week").

### 3. Identify "who is carrying" (ใครแบก) — sector leadership
Bucket the market and note leaders vs. laggards:

| Bucket | Tickers (examples) | Logic |
|---|---|---|
| Oil / E&P | PTTEP, IRPC, IVL | War/supply; play **both** call & put on news |
| Petrochem / anti-commodity | IVL, PTTGC, SCC, SCGP, TOA | Benefit from **falling** oil (input cost) |
| Semiconductor / chips | DELTA, CCET, HANA, KCE | Track NDX/global chips; **buy on dip** |
| Banks | KTB, KBANK, KKP | Rate narrative; **strong leaders but no range → hold, don't trade** |
| Power / utilities | GPSC, BGRIM, GULF | Lower fuel cost; GULF also AI/data-center |
| Construction | STECON, CK | Government stimulus, infrastructure |
| Tourism / airport / hospital / retail | AOT, MINT, BH, BDMS, CRC, CPALL | Peace ⇒ more tourism |
| Livestock (หมูไก่) | BTG, CPF, TFG | Cycle turn + lower logistics cost; cheap/low in range |

**Candidate = ** a leader currently **dipping** to support, **or** a cheap laggard
with a clear catch-up story and "room left" (อัพไซด์ยังเหลือ). Use banks as a
*tell*: when banks are strong, the index is hard to push down.

### 4. Per-stock chart plan
For each candidate, on the **Daily** chart mark:
1. **Orange 20-EMA** (dynamic support in uptrend / bounce target in downtrend).
2. **Base / support zone** (where price last based — "ฐาน").
3. **Resistance / breakout level.**
4. **Confluence:** Master Bar (wide high-volume candle marking a defended zone),
   volume spikes, declining volume into a pullback (healthy), or heavy sell volume
   that *fails to push price down* (possible accumulation).
5. **200-day line** as a deeper structural backstop alongside the 20-EMA.
6. **Open gaps** — mark them as targets/resistance; a gap-up that holds/twists
   (`บิดยัน`) after good งบ is confirmation.
7. **Multi-bottom bases** (double / triple bottom) as high-conviction support.
- Drop to the **60-min** chart for finer entry timing.
- **Pre-earnings shake-out:** recovery names often get knocked down *just before*
  a known report date, then jump if งบ is OK — treat that dip into support as an
  entry, not a breakdown.
- **Fake breakout (`แลบหลอก`):** a poke above resistance that closes red = do not
  chase.
- **Volume around the print:** require declining volume into the pre-print base;
  require rising/peak volume to confirm a post-print breakout; a high-volume
  down-bar that *holds* support = accumulation.

### 4b. Earnings-season overlay (งบ) — when quarterly results are in play

During earnings season, results (`งบ`) become the dominant short-term variable.
Layer this on top of the chart and macro — *"there are more variables than just
looking at earnings."* He is a chart/entry trader, not a fundamental analyst: he
reads **consensus vs. actual and the price reaction**, not balance-sheet internals
(numbers come from broker/aggregator feeds).

**Build an earnings calendar.** For each watchlist name, know its **expected
report date** and whether it has **already reported (`งบออกแล้ว`) or not
(`ยังไม่ออก`)**. Pull **consensus** and compare to actual (or to last year if
uncovered). Tag each: **beat / in-line / miss**, with YoY%, turnaround/record,
dividend/XD.

**Classify the setup:**
- **Reported + beat** → watch for **sell-on-fact (`เซลล์ on fact`)**: good งบ does
  *not* guarantee a green candle (leaders can open red). Don't chase the spike —
  only enter on a clean **dip to support / the orange EMA**.
- **Reported + miss** → **Selling-Climax (SC) play**: the stock is dumped on
  volume, absorbed over 2–3 days (`ซับแรงขาย`) down to an old base where volume
  dries up and bots accumulate. Buy there **only if** the business still profits /
  pays a dividend — a high still-payable yield at the lower price can justify it.
- **Not yet reported** → two choices:
  - *Pre-position (buy before on expectation):* only for a **laggard at base /
    below the EMA** where you judge งบ won't be bad — downside is limited at the
    base. Always with a **structural stop**.
  - *Follow (buy after on confirmation):* if you can't judge the print, **wait,
    let it gap up, then follow** the move.

**Peer read-through (sector dominoes).** When early/small names in a group beat,
**infer** the bigger/later names will follow — set alerts on the group's bellwether
print (e.g. refiners follow the leader's result; retail follows the leader; the
leasing pack moves together). This is *inference*, not reported fact — flag it.

**Print-day risk rule.** *If you can't stomach a gap up **and** a gap down, be flat
before the report.* If holding through, pre-define the stop at the structural level
and **don't negotiate it**.

**IV crush — the DW-specific earnings trap.** Issuers mark a DW's implied
volatility *up* into a known earnings date and *down* immediately after. So a DW
bought right before the print is **expensive (inflated IV)**, and even a correct
directional call can lose money once IV deflates post-announcement. Prefer to
**enter DWs *after* the print** (follow the confirmed move) rather than buy a
pumped-IV DW before it; if you must pre-position, do it in the underlying stock or
a low-IV/longer-dated DW. *(IFEC; ipresage earnings-IV-crush — verified.)*

### 5. Entry rules
- **Trade with the trend, never against the global main trend.**
- **Buy on the dip** to the EMA/base zone — don't chase. "Chasing = getting stuck
  at the top (ดอย)."
- **Wait for a confirming green candle** at support before entering; buying before
  the bounce confirms is gambling (วัดดวง).
- **Breakout entries** only if you're a skilled breakout trader and accept a tight
  stop at the breakout level.

### 6. DW (derivative warrant) selection — expert-grounded

The trader's rules (liquid, "sen" ≥ 0.8, gearing 3.5–5.7×, far expiry) are a
*starting point*. What actually governs your DW return is more precise:

- **Trade on EFFECTIVE gearing, not simple gearing.**
  `effective gearing = simple gearing × delta`. This is the real multiplier — the
  % the DW moves for a 1% move in the underlying. Simple gearing alone (the skill's
  3.5–5.7×) overstates leverage; a high-gearing DW with low delta barely moves.
  *(SET DW intro; warrants.com.hk tutorial06 — verified.)*
- **Pick moneyness deliberately via delta:** target roughly **delta 0.20–0.80**.
  - **Delta > 0.80** (deep ITM): tracks the stock tightly (the trader's "sen ~1"
    preference) but **effective gearing collapses** — you pay mostly intrinsic value
    for little leverage. Good for control, weak for the leverage you're paying for.
  - **Delta < 0.20** (deep OTM): a lottery ticket — high stated gearing but tiny
    delta, and **theta savages it**. Avoid.
  - So the trader's "sen ≥ 0.8" buys *tracking* but sacrifices the leverage edge;
    a balanced swing trade often sits **mid-moneyness (~0.4–0.6 delta)**. Choose
    consciously based on conviction and holding period.
- **Compare expensiveness by IMPLIED VOLATILITY (IV), not price.** Two DWs on the
  same stock: the one with **lower IV is cheaper**. A higher IV makes the warrant
  more expensive and means you need a bigger underlying move just to break even.
  *(IFEC IV page; warrants.com.hk — verified.)*
  - ⚠️ **On the SET, issuer IV is a biased (typically inflated) predictor of
    realized volatility** — i.e. DWs are structurally priced rich. Holding them is
    a *cost*; favor lower-IV series and shorter holds. *(Thai/Malaysian structured-
    warrant study, ScienceDirect S1062976921000612 — verified.)*
- **Time decay (theta) accelerates near expiry.** "Far expiry" is right for theta,
  but the deeper reason is that the time-value bleed is non-linear and worst in the
  final weeks — never hold a near-expiry DW through a slow grind.
- **IV crush around earnings:** issuers mark IV *up* into a known event and *down*
  right after. A correct directional call can still **lose** if you bought a
  pumped-IV DW before the print — see §4b. *(IFEC; ipresage earnings-IV-crush.)*
- **Liquidity / spread:** still pick actively-traded series; the market-maker
  bid-ask spread is a real per-trade cost on top of IV.
- **Tracking sanity check:** DW (child) moves ~4 ticks when the stock (mother)
  moves ~5 — "แม่วิ่ง 5 ช่อง ลูกได้ 4 ปิ๊บ".
- Series are named `ISSUER + STOCK + C/P + YYMM + letter`, e.g. `CPF13C2611A`
  (issuer 13, CPF, **C**all, exp 26-11). Use **P** (put) when the macro favors
  downside.

### 7. Risk & exits
- **Stop loss = a specific structural level** (below the base/support, or the
  failed breakout). Lose it → exit. No hoping.
- **Target = the orange EMA** (downtrend bounce) **or the next resistance band**
  (uptrend). **Sell into resistance; never buy at resistance.**
- **Size by fixed-fractional risk, not "limited capital" gut feel.** Risk a fixed
  small fraction of equity per trade — **~1% (max 2%)** — and back into position
  size from the stop distance: `size = (equity × risk%) ÷ (entry − stop)`. With a
  leveraged DW, compute the risk on the **DW's** worst-case move, not the stock's.
  *(Van Tharp position-sizing; practitioner standard — not independently verified,
  treat as best practice.)*
- **Think in R-multiples.** Define **1R = your stop distance** (the amount at risk).
  Judge every trade by reward-to-risk *before* entering — take setups offering
  **≥ 2R–3R** (e.g. risk ~0.50 for ~2.00 upside = 4R). Track outcomes in R so
  expectancy = `(avg win × win%) − (avg loss × loss%)` stays positive over many
  trades. *(pnlledger R-multiples / expectancy — best practice.)*
- **Systematic exit that actually pays (2026 trade-level + portfolio backtests).**
  The variant that maximised profit on SET100/10y+5y: hold the **full** position and
  **do NOT exit on a close below the EMA before +1R** — that "trend-break" bail cut
  ~84% of trades early and turned the book into a **net loser (PF 0.75)**. Instead, at
  **+1R move the stop to breakeven and let it run** (no fixed take-profit cap); exit
  only on the **structural stop** or — *after* 1R is locked — a **close back under the
  20-EMA** (a trailing exit that can't lose money). Then **cap the book at ~12
  concurrent names** (tighter caps over-concentrate → ~−48% drawdown; wider ones idle
  cash and drag return) and **size bigger into higher-composite leaders** (Q1 1.5× ·
  Q2 1.25× · Q3 1× · Q4 0.75× · Q5 0.5×) — quintile-tilted sizing beat equal-weight on
  Sharpe *and* profit factor in both windows. *Trade-off: let-run + leader-tilt lift
  return but DEEPEN drawdown (~−32% → −41%); it is a right-tail game — many small
  losers, a few big winners — so it needs the discipline to sit through the losers.*
  Add a **market-regime brake**: when the broad index is **below its 200-SMA** (risk-off),
  **halve new position size** — a portfolio backtest showed this trims max drawdown ~9pts
  on both a 10y and 5y window (≈return-neutral on the long window), a cheap drawdown guard
  that matters most with leveraged DWs. *(Shipped in the scanner; `--no-regime-brake` off.)*
- **Hedge by switching sides:** because chosen names have both call & put DWs,
  flip to puts if the macro flips (oil spikes, war flares) and vice-versa.
- **Capital discipline:** you can't buy every good chart — the edge is the *entry
  point*. Don't tie capital up in chased positions ("ดอย") and miss better setups.
- **Tranche in (`ไม้ 2 ไม้ 3`):** scale entries — a first lot at the base, a 2nd/3rd
  "insurance" (`กันเหนียว`) lot at deeper support — instead of one all-in buy.
- **Earnings-event risk:** be flat before a print if you can't take a gap either
  way; tie the stop to a structural level and don't negotiate it.
- **Layer macro over งบ:** even good earnings can be dumped if the macro flips
  (e.g. peace breaks, money rotates out of war-beneficiaries) — `งบดีแล้วโดนเทแบบงงๆ`
  ("good earnings, dumped for no obvious reason"). Check war/peace + key meetings
  before sizing war-sensitive names.
- **Distinguish a miss-dump from a broken business:** a one-off earnings miss is
  often an SC buy at the old base; a genuine growth deterioration eventually breaks
  the base — don't blindly average down (`ถัวกันหน้ามืด`).
- **Never average down a losing leveraged position.** Adding to a loser throws
  good money after bad, enlarges risk past your fixed fraction, and (on a DW) fights
  theta + IV decay at the same time. A pre-planned *tranche-in at support* (above)
  is fine; *rescuing a position that broke its stop* is not. *(investorean — best
  practice.)*

## Output template

When the user asks for a recap or a name, respond in this shape:

```
MACRO: <regime> — oil <up/down>, NDX <near highs/weak>, key events <…>
INDEX: SET <px> vs 20-EMA <above/below>; week range <low>–<high>
LEADERS: <sectors carrying> | LAGGARDS w/ room: <…>

<TICKER> (<sector>) — <call/put> bias
  Trend:    Daily candle <above/below> orange 20-EMA (<level>)
  Earnings: <reported beat/in-line/miss | reports <date>> ; <YoY%, XD, turnaround>
  Setup:    <buy-on-dip | Selling-Climax | pre-position | follow-the-gap>
  Buy zone: <support/base> ; confirm green candle
  Stop:     <structural level>  (1R = entry − stop)
  Target:   <EMA or resistance band>  (≥2R?)
  Size:     <(equity × 1%) ÷ (entry − stop)>
  DW:       <SERIES> — delta <x>, eff.gearing <gear×delta>, IV <vs peers>, exp <month>
  Note:     <volume/Master Bar/gap/peer read-through; IV-crush risk if pre-earnings>
```

## TradingView scripts (Pine v6)

Two companion scripts live in the project root and encode the *tradable* mechanics
(the macro/sector/earnings judgment in §1–§4b still has to be applied by hand):

- **`set-dw-swing.pine`** — live indicator (add to any SET stock or DW chart).
- **`set-dw-swing-strategy.pine`** — backtest version (run on a SET *stock*, Daily).

**How to read the signals:**

| On the chart | Means | Do |
|---|---|---|
| 🟢 **BUY** label (green, below bar) | dip-to-EMA setup confirmed (§5); shows Entry/Stop/TP | enter near support; place the shown stop |
| ⚠ **BUY** label (orange) | same, but earnings are within the IV-crush window (§4b) | prefer entering *after* the print, or use the stock not a DW |
| 🔴 **SELL** label (red, above bar) | exit a long — trend broke under the EMA **or** rejection at resistance (§7) | take profit / cut; don't hold below the orange line |
| Green / red **candles** | uptrend (buy dips) / downtrend (bounce only) — the orange-EMA regime | only look for BUYs when candles are green |
| Red dashed / green dotted **lines** | structural **stop** / **1R & 2R targets** for the active BUY | manage the trade to these rails |
| **ACTION** box (top-right) | plain-language state: BUY / SELL / HOLD / STAND ASIDE + size & DW/earnings flags | the one-glance summary |
| ○ ✕ SC ◆ (advanced mode) | accumulation / fake-breakout / Selling-Climax / past-earnings | context only — turn on by unticking "Simple mode" |

Inputs you must supply per name: account **equity & risk %**, and for a DW the
**gearing + delta** (from the warrant card) and **next earnings date** (broker
calendar — Pine can't fetch upcoming earnings). Alerts exist for BUY, SELL,
Selling-Climax, accumulation, and IV-crush. **Backtest caveat:** the strategy
tests chart+risk mechanics only — it does *not* model DW leverage, IV/theta, or the
discretionary macro/earnings context, so treat its stats as the *underlying's*
trend-edge, not the DW's.

## Daily scanner & alert (Python — reads official SET data)

Project-root tooling that runs the BUY(dip) signal on a live universe. Same logic
as the `.pine` defaults (single source of truth in `setdw_signal.py`).

- **`scan_dip.py`** — screens a universe file, prints the names that fired with
  entry/stop/T1/T2/size + a CSV. Run via the `./scan` wrapper (self-heals the venv).
  `./scan` · `./scan --asof 2026-06-24 --sort dist` · `./scan --concurrency 6 --cache-hours 12`
- **`set_data.py`** — the **default data source is the official SET** (set.or.th),
  not Yahoo. The SET API is behind an Incapsula WAF, so a headless Chromium
  (Playwright) clears the challenge once and fetches all symbols **concurrently** in
  one session (`fetch_all`, `--concurrency` default 6; retries + re-warms on a 403 so
  one bad name can't kill the batch; `--cache-hours` serves `data/<SYM>.csv` without
  the network). It merges two SET endpoints (`historical-trading` = real OHLCV but
  ~118-bar cap + `chart-quotation` = ~241 close-only bars) so SMA200 warms up;
  close-based indicators are exact, ADX/ATR are indicative. `--source yahoo` falls back.
- **`alert.py`** — evaluates a **watchlist** (`watchlist.txt` or `--symbols`) on the
  latest closed bar; per-name verdict to `alert.log` + one summary notification on a
  fire. Scheduled by a launchd agent (weekdays 17:30 ICT). Manage with
  `launchctl … gui/$(id -u)/com.klang.kce-alert`; exit 1 = nothing fired (normal).
  (`alert_kce.py` is a deprecated KCE-only shim.)
- **`positions.py`** — the **stateful managed BUY/SELL watchlist** (`positions.json`).
  Turns the daily scan into a persistent book: a BUY(dip) hit enters and is **held** (no
  early EMA/below-entry exit — that was a net loser); at **+1R** the stop moves to
  breakeven and it **runs** until it loses the 20-EMA or hits the structural stop; each
  T1/sell event is shown **once** then dropped the next day. The book is **capped**
  (`scan_dip --max-positions`, default 12) to the strongest names by composite (weak new
  hits are skipped, over-cap holdings rotate out), and each position is **size-tilted by
  composite quintile** (Q1 1.5× … Q5 0.5×). `scan_dip.py` (sole writer, run with
  `--composite`) writes it; `alert.py` reads it into the LINE brief. Empirically tuned in
  `bt_exits.py` (exit rules) + `bt_portfolio.py` (cap & sizing) — see the backtest section.
- **`test_signal.py`** — parity/drift guard for `setdw_signal` (golden-master + an
  independent Wilder-RSI cross-check on `tests/fixture_kce.csv`). Run after refactors.
- **`profiles.py`** — per-stock signal overrides (only forward-validated ones):
  KBANK/KTB/DELTA use `rsi_min=60` (stable banks/trender); **KCE uses `vol_mult=1.5`**
  (a behavior study found volume-surge is its #1 real-vs-fake tell — forward-validated
  vol≥1.5× lifts win% 60→75%). Everyone else the global defaults. Applied by
  `scan_dip.py`/`alert.py`; `--no-profile` disables. Don't add a name without
  walk-forward/forward-validation evidence — blanket per-stock tuning overfits.
- **`costs.py`** — first-principles SET transaction cost from the exchange **tick-size table**
  (`side_cost(price) = commission 0.157% + ½ quoted spread`). Realistic per-name cost is
  0.32–0.49%/side — the old flat 0.3% was optimistic. Also `trailing_turnover()` +
  `spread_ticks_for()` for the **liquidity gate**: `scan_dip --min-turnover` (default **฿10M/day**)
  drops thin BUY(dip) hits, because a backtest showed thin names' wide 2-tick spreads *kill the
  edge* (see the cost finding below).
- **`collect_nvdr.py`** — appends the daily per-stock **NVDR (foreign-proxy) net flow** snapshot to
  `nvdr_history.csv` (folded into `daily_scan`, best-effort). The SET only serves the latest session
  (no history), so this ACCUMULATES a series forward to one day test NVDR flow as a 3rd weak signal.
  Until months of data exist it is **live context only, not a mechanical filter**.
- **`bt_exits.py` / `bt_portfolio.py`** — the research harness. bt_exits = trade-level exit rules;
  bt_portfolio = the full managed book (entry/sizing/cap/overlay/**cost-model**/liquidity), with
  `--cost-model {flat,tick,tickliq}`, `--min-turnover`, `--entry`, `--overlay`, sizing sweep. Use
  these to test any new hypothesis on BOTH a 10y and 5y window before believing it.

Still a CANDIDATE list — the macro/sector/earnings judgment (§1–§4b) and DW
selection (§6) remain manual. Data is EOD; run after the 16:35 ICT close. The venv
lives in `~/.venvs/trading-dr` (`./scan` rebuilds it if missing/broken).

## Own backtest — does the mechanical core actually pay?

A replica of `set-dw-swing-strategy.pine` was run in Python on **25 liquid SET
names over 10 years** (Yahoo data, costs 0.157%/side + slippage). Sobering results
that should temper conviction in the chart rules alone:

- **The naked mechanical strategy is ~break-even-to-negative after costs.**
  Fixed-size: **−19% / PF 0.91 / 43% max drawdown.** Risk-1%-sized: **−5% / PF 0.80
  / 6.5% max DD.** Win rate ~34%. A smaller 5-name/5-year run looked positive
  (+13%, PF 1.52) — that was **small-sample optimism**; the broad/long test is the
  trustworthy one.
- **Sizing dominates the signal.** Switching fixed-units → risk-1% didn't create
  edge (it can't) but cut the loss to ¼ and **max drawdown from 43% → 6.5%.** This
  is the most transferable lesson: *how you size matters more than the entry.*
- **The `close < EMA` trend-break exit was a net drag.** Removing it flipped the
  system from PF 0.80 → **1.09 (+1%, win% 49%, 1.8% maxDD)** and cut trades ~70% —
  it was bailing on every minor whipsaw below the orange line. → **Default it OFF**
  in the strategy; let the structural stop + R-targets work. Still only marginal,
  not a money machine.
- **Win-rate tuning (now the script defaults).** Adding a momentum/quality gate
  (**RSI(14) ≥ 55** + **200-SMA rising**), closer targets (**1R / 1.5R**), and
  **breakeven stop after T1** raised win rate to **~61% while keeping PF 1.11**
  (avgR +0.03, maxDD 1.5%). Note the trade-off: *just* shrinking targets to 1R/1.5R
  without the filters inflates win% to ~63% but **collapses PF to ~0.99** (zero
  expectancy) — higher win rate is only worth it when expectancy stays positive.
- **Per-stock optimization (DELTA / RCL / HANA, full history + 70/30 OOS).** Strong
  trenders score far higher than the broad basket and *hold out-of-sample*:
  DELTA **75% win OOS**, RCL **89–90% OOS** (but only ~10 OOS trades — cyclical
  shipping, high gap risk), HANA only **60% OOS** (IS 70% → a live overfit-warning).
  Universal levers confirmed across all three: **RSI ≥ 60–65, 200-SMA rising,
  breakeven after T1** — and for DELTA/RCL *don't* filter "extended" (they run far
  from the EMA).
- **Accuracy add-ons (validated OOS, now in the scripts).** **ADX(14) ≥ 20** is the
  most robust universal booster — only trades when a real trend exists; it rescued
  the weakest name (HANA OOS 45→58%) and helped the others → **default ON**.
  **"Prior bar red"** (buy a true red-candle dip) is excellent for clean trenders
  (DELTA 84%/87% OOS) but hurts gap-up names → optional. **"Volume > average"**
  (demand confirmation) helps volatile names (RCL) → optional. *"Touch-EMA-exactly"
  was tested and DROPPED — it lowered accuracy everywhere.*
  Per-stock starting points: DELTA `RSI60, +prior-red, 1R/2R, stop12`; RCL `RSI65,
  +volume, 1R/2R, stop12`; HANA `RSI60, ADX≥20, 1R/1.5R, stop10–12`.
- **One name (DELTA) carried both modes.** Strip the single best trender and the
  system is clearly negative → the method is a bet on catching rare strong trends
  while bleeding on the rest (consistent with the academic "profit from winners,
  weak timing" finding below).
- **Managing the OPEN trade — the 2026 trade-level + portfolio study (`bt_exits.py`,
  `bt_portfolio.py`, SET100, 10y + 5y).** How you *exit and size* swung the result far
  more than the entry: (1) The shipped **"let winners run"** exit — no close<EMA/below-
  entry exit before +1R (the old rule was a net **LOSER, PF 0.75**, bailing 84% of trades
  early), breakeven at +1R, **no take-profit cap**, trail the EMA only afterwards → **PF
  1.26 / +0.93% per trade** (1.34 with a composite-Q1 filter, an identical +1.33%
  expectancy in *both* windows). Capping targets at 1.5R (the older default) *threw away
  the right tail.* (2) At the portfolio level a **cap of ~12 names** is the knee (top
  Sharpe/PF, DD −33%; caps ≤8 over-concentrate to −48% DD, ≥20 drag on idle cash). (3)
  **Composite-quintile position sizing** (Q1 1.5× … Q5 0.5×) beat equal-weight on Sharpe +
  PF in both windows — overweighting leaders pays. *Sobering portfolio reality: even the
  best config is ~5% CAGR with −30%+ maxDD (survivorship-inflated); a 1.2–1.3 per-trade PF
  does NOT compound into big returns because the book is often under-deployed and drawdowns
  are deep — the edge is thin, real, and right-tailed, not a money machine.*
- **Transaction cost & execution are FIRST-ORDER (the 2026 Medallion-informed study).** A
  per-name cost model (`costs.py` — SET tick-size half-spread) rebuilt the same book under
  realistic costs: as a **patient LIMIT trader** (rest at the touch, don't cross) the edge is
  Sharpe ~0.6; as a **market TAKER** crossing the spread it halves; on **thin 2-tick names it dies
  (PF < 1)**. Execution style + name liquidity matter MORE than the signal. → **Always place a limit
  at the signal close and let it come to you — never chase a gap up** (that discipline is worth the
  whole edge, not just niceness); and **stay in liquid names** (the `--min-turnover ฿10M/day` gate).
  A light liquidity gate helps; a heavy one over-filters and hurts.
- **★ CORE CONCEPT — what actually survived testing (and what didn't).** After stress-testing every
  tempting idea on BOTH a 10y and 5y window, the **validated core** is: *buy-the-dip (mean-reversion)
  entry · composite mom+trend leader ranking · let-winners-run exit (breakeven at +1R, trail the EMA
  after, no target cap) · ~12-name cap · composite-quintile position sizing · a below-200-SMA regime
  brake · patient limit execution on liquid names.* Things that **sounded good but tested NEGATIVE
  and were rejected**: switching entry to breakout (great on 10y, collapses on 5y — survivorship/
  regime), `dip∩breakout` and `dip∪breakout` (worse or fragile), vol-target / drawdown / regime
  *exposure overlays* (de-risk away return, no free Sharpe), and fractional-Kelly / inverse-vol
  sizing (backfires because in a momentum book high-vol names ARE the high-edge leaders). The
  lesson: the multi-window discipline repeatedly caught survivorship/overfit traps — **most "clever"
  additions don't help; the edge is thin, and protecting it (cost, liquidity, no-overfit, sitting
  through many small losers) matters more than adding cleverness.**
- **Caveat:** these 25 all *survived* to today — survivorship bias makes the test
  **flattering**, so live results are likely worse. DW leverage/IV/theta not
  modeled (would amplify losses). Bottom line: **the chart mechanics alone don't
  pay; any real edge requires the discretionary macro/sector/earnings layer (§1–§4b)
  plus disciplined risk sizing (§7), and — newly — rigorous cost/liquidity/execution
  discipline (trade as a patient limit trader on liquid names).**

## Evidence base — what research supports vs. folklore

Findings from a verified deep-research pass (25 claims fact-checked, 0 refuted).
Use these to weight conviction; they are about *base rates*, not any single trade.

- **The EMA/trend core is empirically supported on the Thai SET specifically.**
  Moving-average / trend rules have been **net-profitable after costs on the SET**
  (an emerging market), unlike most developed markets where costs erase the edge.
  *(Tharavanij 2015, Springer s40064-015-1334-7; Fifield 2008, Tandfonline.)*
  → Keep the orange-EMA trend filter; it's the most defensible part of the method.
- **But the edge comes from catching big trends, not precise timing.** The profit
  is in *riding winners*, while the rule's *market-timing* skill is weak. → Let
  winners run to resistance; don't over-trust pinpoint dip entries. Across 92
  studies, TA results are "mostly positive but methodologically flawed" and shrink
  once realistic transaction costs are added. *(Park & Irwin 2004, farmdoc.)*
- **DW returns are driven by effective gearing (gearing × delta) and IV, not the
  headline gearing number** — see §6. *(SET; warrants.com.hk — verified.)*
- **DW implied volatility on the SET is a biased (inflated) vol predictor** — DWs
  are structurally priced rich, so holding time is a cost. *(ScienceDirect
  S1062976921000612 — verified.)*
- **IV crush is real around earnings** — buying a DW before a known print overpays
  for IV that deflates after. *(IFEC; ipresage — verified.)*
- **Not verified here (lower confidence — treat as hypotheses):** post-earnings-
  announcement drift (PEAD) *on the SET specifically*, the precise sector-rotation
  drivers (oil/baht/foreign-flow/MSCI weighting), and the position-sizing numbers
  (1%/2R came from practitioner sources, not SET studies). The earnings peer
  read-through and "who carries the index" theses remain **the trader's inference.**
- **Vintage caveat:** the TA studies span ~1989–2013; market microstructure and
  costs have since changed. Re-test before relying on any specific edge.

## Honest limitations (from the source)

- The trader's own technique is deliberately **thin and repeatable**: one EMA trend
  filter + price structure + structural stop + DW specs. The position-sizing,
  effective-gearing/IV, R-multiple, and evidence sections above were **added from
  external research**, not from the streams.
- Macro/sector reasoning is **qualitative** and often quotes brokerage analysts
  (e.g. Kasikorn Securities), not original analysis.
- The **earnings angle is real but shallow on fundamentals** — it is consensus-beat
  + price-reaction + chart, not financial-statement analysis. The presenter
  delegates the numbers to broker/aggregator feeds and admits he hasn't checked the
  internals. Consensus, report dates, and peer read-throughs are **forecasts/
  inference**, not confirmed results — verify each before acting.
- All tickers/levels here are **examples from specific streams** — re-derive
  everything from live data. Markets change; verify before acting.
- This is **education/structure, not advice.** Surface assumptions; the user
  decides and bears the risk.

## Sources

**Primary method** — YouTube livestreams by **DW Trader** (`#Liveล่าหุ้น`):
- *"ใครแบกบ้าง? Recap หุ้นพา SET จ่อ 1600..ตัวไหนอัปไซด์ยังเหลือ?"* (21 Jun) —
  macro/sector + technical method · `https://www.youtube.com/watch?v=nL8Iu_Sodlg`
- *"งบดีมีของ พร้อมจุดเข้า — ข้อมูลลับงบหุ้น ก่อนคนแห่เข้า"* (9 May) —
  earnings-season stock-picking · `https://www.youtube.com/watch?v=n7Yi_Ildziw`

**Expert grounding** — verified deep-research pass (24 sources, 25 claims fact-checked):
- DW mechanics: SET DW intro (`set.or.th/en/market/product/dw/introduction`);
  warrants.com.hk tutorials 04/06; IFEC implied-volatility page.
- DW IV bias on SET/Malaysia: ScienceDirect `S1062976921000612`.
- TA evidence: Tharavanij 2015 (Springer `s40064-015-1334-7`); Fifield 2008
  (Tandfonline `10.1080/09603100701720302`); Park & Irwin 2004 (farmdoc AgMAS04_04).
- Earnings IV crush: ipresage earnings-IV-crush. PEAD: Bernard & Thomas.
- Risk/sizing (practitioner, unverified): Van Tharp Institute; pnlledger
  R-multiples; investorean (averaging-down).
