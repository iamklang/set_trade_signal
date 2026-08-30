---
name: quant-meta-label
description: >-
  Build/operate a meta-labeling ML layer on top of the existing dip_or_brk
  primary signal (SET DW Swing + US swing) — triple-barrier labels, sample-
  uniqueness weighting, purged CV, and a secondary probability used as a
  gate + size input. Bakes in the fixes for small-sample, precision-only,
  equity≠DW, and US-only-edge constraints. Use when adding an ML precision
  filter to buy_signal, or asked about meta-labeling / triple-barrier / López
  de Prado ML for this system. Part of the SET DW Swing system (see also:
  /quant-validation, /set-dw, /set-risk).
---

# Quant Meta-Labeling — precision layer over the primary signal

López de Prado Pillar 4, wired to THIS repo. The mechanical `buy_signal()` is
already a high-recall **primary model** (picks the side). Meta-labeling adds a
**secondary** binary model that predicts *whether this specific trigger will
reach +1R before its stop* — used only as a **gate + size input**, never to
invent signals. See [[quant-knowledge-base]] Pillar 4. Validate through
[[quant-validation-skill]] before trusting anything.

> Golden rule: meta-labeling can only raise **precision** (cut/shrink weak
> triggers). It cannot create edge. If the secondary adds nothing on purged CV,
> the correct outcome is to **fall back to the primary unchanged** — that is a
> success (honest no), not a failure.

---

## Where it plugs into the code

| Piece | Existing code | Role |
|-------|---------------|------|
| Primary (side) | `setdw_signal.buy_signal(df, cfg)` | high-recall trigger — unchanged |
| 3 barriers | `trade_plan()`: `t1=close+1R`, `stop=llStop`, ~20d hold | become the label |
| Features (X) | `add_indicators()` + `composite.cross_section_scores()` + `exposure_overlay()` | model inputs |
| Cost/net check | `costs.py` | net-of-cost validation |
| Live wiring | `scan_dip.py` / `alert.py` after the trigger fires | apply p as gate+size |

### Label (triple-barrier)
```python
def triple_barrier_label(df, i, stop, t1, vbar=20):
    """1 if High hits t1 before Low hits stop within vbar bars, else 0."""
    for _, bar in df.iloc[i+1:i+1+vbar].iterrows():
        if bar.Low  <= stop: return 0
        if bar.High >= t1:   return 1
    return 0   # time barrier = not a win
```
Barriers already scale per-name because `riskU = close − llStop` tracks each
name's structural volatility — no separate ATR sizing needed.

### Features (all already computed)
`rsi, adx, distPct=(close-ema)/ema, vol_ratio=Volume/volSma, riskU/close,
z_mom, z_trend, z_lowvol, quintile, mkt_vol, risk_off` — plus a `market`
dummy (SET=0/US=1) only if pooling (see Fix 1).

### Apply live
```python
p = secondary.predict_proba(X)[:,1]      # P(reach +1R before stop)
if p < P_GATE:  skip                      # gate: drop weak setups
plan = apply_size_tilt(plan, quintile)    # keep the cross-sectional tilt
plan["size"] = int(plan["size"] * meta_mult(p))  # multiply, don't replace
plan["meta_p"] = round(float(p), 3)       # persist to positions.json for audit
```
`meta_p` (per-trade timing quality) is **orthogonal** to the quintile tilt
(cross-sectional leadership) — they multiply, they don't overwrite.

---

## The four constraints — and the fix baked into the build

### Fix 1 — Small sample → pool + weight + shrink
- **Train on yfinance long history (≥12y), not `set_data`** (which serves ~1yr).
- **Pool the whole universe cross-sectionally**: stack every name's triggers
  into one dataset (the label is per-trigger, so N grows with names × time).
- Optionally pool **SET ∪ US** with a `market` dummy feature — more labels,
  but only if a `market`-interaction check shows the pattern generalizes.
- Report **effective sample size = Σ sample-uniqueness weights**, never the raw
  row count — overlapping 20-day labels inflate raw N badly.
- Keep the secondary **small & regularized**: shallow gradient boosting /
  random forest, ≤ the features above, `min_samples_leaf` high, and
  **monotonic constraints** where sign is known (higher adx/z_mom ⇒ not-lower p).

### Fix 2 — Precision-only → gate+size with graceful fallback
- Use p strictly as (a) a **gate** (skip if `p < P_GATE`) and (b) a **size
  multiplier**. Never let the secondary generate an entry the primary didn't.
- **Validate the primary has edge first** (Pillar 1: dip+quintile does) before
  layering a secondary on top.
- If purged-CV shows the secondary does **not** beat "take every primary
  trigger" net of cost, **auto-degrade to primary-only** (`meta_mult ≡ 1`,
  `P_GATE = 0`). Wire this as a config switch, default OFF until it earns ON.

### Fix 3 — Equity ≠ DW → theta-aware label + separate instrument layer
- Label on the **underlying equity** move (that is what the chart signal
  predicts), but:
  - **Shorten the vertical barrier** for the DW book (theta bleeds time) — test
    `vbar` ∈ {10, 15, 20} and prefer the shortest that keeps precision.
  - Require the equity target to clear a **theta-survival threshold**: a +1R
    equity move must be large/fast enough that the geared DW still nets positive
    after theta + IV crush. Derive that threshold via `/set-dw` (effective
    gearing, delta, days-to-expiry), not from the equity backtest.
- Keep **instrument selection separate**: `meta_p` filters the *equity setup*;
  which DW series to buy (moneyness/gearing/IV) stays in `/set-dw`; US options
  analog in `/us-options`.

### Fix 4 — Edges are US-only → separate models + mandatory local re-test
- Pillar-4 *methodology* is market-agnostic, but *results* are not. **Train
  separate SET and US secondaries** (do not assume the SET model transfers), or
  pool with the `market` dummy AND prove generalization.
- Everything ships only after clearing [[quant-validation-skill]] **Gate 5**
  (SET/DW-local re-test net of Thai cost + gearing). A US-trained precision
  gain is a hypothesis for SET, never a deployment.

---

## Build order (each phase gated by /quant-validation)

```
Phase 1  meta_label.py: build_dataset(frames,cfg) → X, y, uniqueness weights
         (reuse buy_signal + trade_plan + composite; write labelled CSV) + tests
Phase 2  train + HONEST validate: uniqueness weights, PURGED K-fold + embargo,
         MDA importance (not MDI), Deflated Sharpe — run /quant-validation
Phase 3  wire into scan_dip/alert: p as gate + size, persist meta_p, config
         switch defaulting OFF (Fix 2 fallback)
```

## Definition of done (else discard)
1. Net-of-cost **precision** of accepted BUYs rises on **purged CV** (not raw split).
2. **Deflated Sharpe** still positive after counting trials (Gate 1).
3. Effective N (Σ uniqueness) is large enough to trust — state it explicitly.
4. Survives a **DW-theta-adjusted** re-test, not just the equity label (Fix 3).
5. If any of the above fails → **fall back to primary-only** and say so.

## Anti-patterns (auto-reject)
- `train_test_split` / plain K-fold on overlapping labels → leakage (use purge+embargo).
- MDI/`feature_importances_` for selection → biased; use MDA.
- Deep nets / hundreds of features on a few-hundred-label set → overfit.
- Reporting accuracy instead of net-of-cost precision + DSR.
- Letting `meta_p` overwrite the quintile tilt instead of multiplying it.
- Deploying a US-trained model on SET without Gate 5.
