---
name: us-macro
description: >-
  Top-down macro reading for US (S&P 500) swing trading — Fed/rates regime,
  index trend (SPX/NDX Daily 20-EMA), breadth, and sector leadership. Use when
  the user wants a market recap, sector-rotation view, or "what's leading"
  analysis. Part of the US swing system (see also: /us-entry, /us-earnings,
  /us-options, /us-risk, /us-evidence).
---

# US Macro & Sector Reading

Top-down workflow (SET method ported to US). Read the macro first, then the
index, then find who's leading.

> Not financial advice — a structured checklist. All levels are examples;
> re-derive from live data.

## 1. Read the macro driver

- **The Fed / rates path** is the pivotal US driver (the analog of SET's oil):
  - **Falling real yields / dovish Fed / rate-cut odds up** → risk-on; bullish
    long-duration growth (tech, biotech, small caps, homebuilders, REITs).
  - **Rising yields / hawkish / sticky inflation** → risk-off; favor value,
    energy, financials, cash-flow quality; growth de-rates.
- **Key events / data:** FOMC dates + dot plot, CPI/PCE, NFP jobs, ISM, 10Y
  yield (the tell), DXY dollar, credit spreads, quad-witching / index rebalances.
- **VIX regime:** <15 complacent trend-friendly; 15–25 normal; >25–30 stress
  (halve new risk, expect whipsaw). Rising VIX + falling SPX = de-risk.
- **Mega-cap breadth:** is the index carried by a few names (narrow, fragile) or
  broad (healthy)? Check equal-weight (RSP) vs cap-weight (SPY), % of names above
  their 50-DMA, new-highs vs new-lows.
- Decide the **regime**: *risk-on / cuts coming* vs *risk-off / higher-for-longer*.
  This sets sector direction and call vs put bias.

## 2. Check the index regime (SPX + NDX)

- Is price **above or below the Daily 20-EMA**?
  - **Above → uptrend** → buy dips toward the EMA/support.
  - **Below → downtrend** → only play bounces; sell into the EMA.
- Confirm with the 50-DMA / 200-DMA structure. State a plain range call
  (e.g. "SPX 5,400–5,600 this week; 20-EMA 5,480 is the line").

## 3. Identify sector leadership (who's leading) — GICS buckets

| Sector (ETF) | Tickers (examples) | Logic |
|---|---|---|
| Tech / semis (XLK, SMH) | NVDA, AMD, AVGO, MSFT, AAPL | AI capex, rates-sensitive growth |
| Communication (XLC) | GOOGL, META, NFLX | Ad cycle, mega-cap breadth |
| Consumer disc. (XLY) | AMZN, TSLA, HD, NKE | Rate-sensitive, consumer health |
| Financials (XLF) | JPM, GS, BAC, V, MA | Yield curve, credit, buybacks |
| Energy (XLE) | XOM, CVX, COP | Oil/gas; inflation hedge |
| Health care (XLV) | UNH, LLY, JNJ | Defensive + GLP-1 growth |
| Industrials (XLI) | CAT, GE, BA, UBER | Cycle, reshoring, infra |
| Utilities/REIT (XLU, XLRE) | NEE, PLD | Rate-sensitive defensives; AI-power |
| Staples (XLP) | PG, KO, COST | Defensive when risk-off |

**Candidate** = a leader currently **dipping** to support, **or** a laggard with
a clear catch-up catalyst and room left. Use **financials + semis** as the tell:
when they lead, the tape is hard to push down; when defensives (XLU/XLP/XLV)
lead, risk appetite is fading.

## Output template

```
MACRO: <regime> — Fed <dovish/hawkish>, 10Y <up/down>, VIX <level>, breadth <broad/narrow>
INDEX: SPX <px> vs 20-EMA <above/below>; NDX <...>; week range <low>–<high>
LEADERS: <sectors leading> | LAGGARDS w/ room: <…>
```

## When to use

- "Market recap / what's leading this week?"
- "SPX above or below trend? Range this week?"
- "Fed turned dovish — which sectors benefit?"
- "Is the rally broad or just mega-cap?"
