---
name: us-evidence
description: >-
  Evidence base and honest limitations for the US (S&P 500) swing system — what
  is (and is NOT) validated when porting the SET-tuned edge to US equities. Use
  when the user asks "does this work on US", wants the edge/limitations, or
  questions whether to trust it. Part of the US swing system.
---

# US Swing — Evidence Base (read this first)

The mechanical core is the **SET-validated** method. On US it is **out-of-sample
and unproven**. This skill exists to keep conviction honest.

> The honest headline: **we ported logic, not a validated US edge.** Trade small,
> log everything, and let US earn its own track record before sizing up.

## What carries over (mechanism, not proof)

The SET backtests validated these as *mechanisms*; they are plausible on US but
NOT re-measured here:

- Buy-the-dip (mean-reversion) + 20-day breakout entry
- Composite momentum+trend leader ranking
- Let-winners-run exit (breakeven at +1R, trail the EMA, no target cap)
- ~12-name cap; composite-quintile position sizing (Q1 1.5× … Q5 0.5×)
- Patient limit execution on liquid names

## What MUST be re-validated on US before trusting

- **Does the 20-EMA dip/breakout edge even exist on S&P 500 names?** US large-caps
  are more efficient than SET100; the mean-reversion + trend edge may be smaller
  or gone after costs. Run the walk-forward on US data.
- **The RSI≥55 / ADX≥20 thresholds** were tuned on SET — re-fit on US.
- **The quintile-tilt magnitudes** (1.5×…0.5×) — re-check the cross-sectional
  spread on US.
- **Cost assumptions:** US is ~$0 commission with penny spreads (much cheaper than
  SET) — that HELPS, but options add IV/theta/assignment costs the stock backtest
  ignores.
- **Regime/exposure overlay** (voltgt/ddbrake) — re-tune to US vol (VIX) levels.
- **Sector-rotation & earnings read-throughs** — entirely US-specific inference,
  never backtested.

## US-specific risks the SET backtest never modeled

- **Bigger earnings gaps** — US single-stock prints gap 10%+; stops slip through.
- **Options leverage** — IV crush, theta, assignment, expiry cliffs amplify losses.
- **Mega-cap concentration** — the S&P 500 is top-heavy; "breadth" and index
  regime can diverge sharply from the average name.
- **Higher efficiency** — crowded, well-arbitraged names give up less edge.
- **PDT / settlement** — capital-use constraints under $25k (see `/us-risk`).

## Academic priors (weak, directional)

- Cross-sectional **momentum** and short-horizon **reversal** are documented on
  US equities, but both have **decayed** and shrink after realistic costs — the
  edge is thin and regime-dependent.
- Trend-following on indices is real but noisy at the single-name Daily scale.
- **None of this is a validated version of THIS system on US** — treat as prior,
  not proof.

## How to earn the track record

1. Run the walk-forward backtest on the US universe (adapt `backtests/bt_*.py` to
   `us500.txt` + US costs) before sizing up.
2. Paper / tiny-size for a quarter; review with `/us-risk` + quarterly review.
3. Compare live expectancy vs the SET book — if US doesn't clear its costs,
   it doesn't get capital.

## The bottom line

Same disciplined machine, **new and unproven market.** The value here is the
*process* (find leaders, buy dips/breakouts, let winners run, size by risk,
review by quarter) — not a promise that the SET edge transfers. Protecting
capital while US proves itself matters more than any single trade.

## When to use

- "Does this strategy work on US stocks?"
- "Can I trust the same thresholds on S&P 500?"
- "What's different / riskier vs the SET system?"
- "What do I need to validate before sizing up?"
