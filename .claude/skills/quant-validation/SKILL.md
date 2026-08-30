---
name: quant-validation
description: >-
  Anti-overfitting validation gate for the SET DW Swing + US swing systems —
  Deflated Sharpe (trial count), purged/embargoed CPCV instead of hold-out,
  Ornstein-Uhlenbeck stop/target instead of grid-search, and mandatory
  SET/DW-local re-test. Use BEFORE trusting any backtest number, adopting a
  new config/parameter, or greenlighting a discretionary edge — this is the
  "honest no" gate. Part of the SET DW Swing system (see also: /set-evidence,
  /set-risk).
---

# Quant Validation — the overfitting gate

Runs the López de Prado / Bailey validation discipline against any proposed
edge. The default answer is **no** until a claim survives every gate below.
Backtest overfitting is the #1 way a systematic book dies — a good-looking
Sharpe is worthless until it clears trial count, leakage, and out-of-sample.

Evidence base: [[quant-knowledge-base]] Pillar 2 (deep-research, verified
3-vote). All cited edges are US/global — **nothing is SET/DW-validated**, so
Gate 5 is non-negotiable. Backs the "honest no" ([[user-crosscheck-discretionary]]).

---

## When to invoke

- A new config, filter, or parameter is proposed ("what if we add X / change Y")
- Someone quotes a backtest Sharpe / CAGR / PF as reason to deploy
- A discretionary name is being justified by "it backtests well"
- Reviewing whether the live config still earns its place (quarterly)

---

## The 5 gates (a claim must clear ALL)

### Gate 1 — Trial count → Deflated Sharpe Ratio (DSR)
Ask first: **how many variations were tried to arrive at this one?**
- With ~5y of daily data, **~45 independent trials manufacture a chance
  Sharpe ≥ 1.0** even when true edge is zero (Bailey-Borwein-LdP-Zhu).
- Count *every* knob swept historically (entry variants, vol_mult sweep,
  exit rules, regime brakes...) — the danger zone is cumulative, not per-test.
- Require a **Deflated Sharpe Ratio** that adjusts the observed Sharpe for
  trial count, sample length, skew, and kurtosis. A raw Sharpe with an
  unknown trial count is **not evidence**.
- 🚩 Auto-reject: any Sharpe of ~5–8 over a window < ~1y = window luck, not
  edge (even the TradingAgents authors disown their own such numbers).

### Gate 2 — Hold-out is NOT enough
- A single in-sample/out-of-sample split **does not control for trial count** —
  you can find a strategy that looks good on BOTH IS and OOS yet has no skill.
- Overfitting a series *with memory* produces **persistent losses**, not just
  zero expected return. "It also worked OOS" is a weak defense, not a pass.

### Gate 3 — Purged + embargoed Combinatorial Purged CV (CPCV)
- Replace single walk-forward with **CPCV**: many train/test recombinations
  yielding a **distribution of Sharpe paths**, not one number.
- **Purge** samples whose labels overlap the test window; **embargo** a buffer
  after each test block. With ~20-day holds, label overlap is large — leakage
  here silently inflates every metric.
- Judge the **worst-decile path and the spread**, not the mean.

### Gate 4 — Stop/target from OU fit, not grid-search
- Do **not** grid-search stop-loss / profit-take on the backtest — that is
  overfitting by construction (Carr & López de Prado).
- Instead fit the strategy's P&L as a discrete **Ornstein-Uhlenbeck** process
  (estimate σ, φ by OLS), simulate ~100k paths over a stop×target mesh, take
  the Sharpe-maximizing pair.
- If φ → 1 (near random walk, long half-life) there is **no optimal rule** —
  the correct output is "no stop rule is justified," not the mesh cell that
  happened to win. Report that honestly.

### Gate 5 — SET/DW-local re-test (mandatory)
- Every edge in the knowledge base is US/global equities & futures.
- Before deploying on SET: re-test **net of Thai transaction costs, board-lot
  (100) constraints, liquidity, and DW gearing / IV crush / theta**.
- A US result is a hypothesis for SET, never a conclusion. Cross-check against
  [[backtest-500d-validation]] and [[volume-confirmation-validation]].

---

## Output format

Give a verdict per gate, then a single call:

```
Gate 1 (DSR/trials):  PASS / FAIL — <trial count, deflated Sharpe or "unknown">
Gate 2 (hold-out):    PASS / FAIL — <is trial count controlled?>
Gate 3 (CPCV):        PASS / FAIL — <path distribution / worst decile>
Gate 4 (OU stop):     PASS / FAIL / N-A — <φ, half-life, or grid-search flag>
Gate 5 (SET-local):   PASS / FAIL — <net-of-cost DW re-test done?>
─────────────────────────────────────
VERDICT: DEPLOY / RE-TEST / REJECT
```

Default to **REJECT** or **RE-TEST** when a gate is "unknown." An unquantified
edge is a rejected edge. Say the honest no.

---

## What already cleared this gate (don't re-litigate)

The live config (`dip_or_brk` + quintile tilt + volume gate) is 500d-validated
net of tickliq cost (CAGR 23.6%, Sharpe 1.65, PF 2.45). The volume gate is the
single most load-bearing filter; `vol_mult > 1` was correctly REJECTED as a 10y
mirage. See [[algo-config-2026q3]]. New proposals must clear the same bar.

## Highest-value next experiment

**Meta-labeling** the existing `dip_or_brk` signal: keep the current trigger as
the high-recall primary model, train a secondary binary classifier to decide
bet/no-bet and size. Validate the secondary model through Gates 1–5 (triple-
barrier labels, purged CPCV). See [[quant-knowledge-base]] Pillar 4.
