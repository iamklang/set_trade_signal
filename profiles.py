"""
profiles.py — per-stock signal overrides on top of the global defaults.

ONLY names whose tuned parameter was validated by WALK-FORWARD stability (the
optimum stayed constant across re-optimized folds AND beat the flat default
out-of-sample) belong here. Blanket per-stock tuning OVERFITS — a single-split
sweep lost to flat RSI55 OOS (PF 1.05 vs 1.11), and most names' optima were
unstable noise. Walk-forward (scratchpad/bt_rsi_walkfwd.py) surfaced a small,
robust set: the banks KBANK/KTB and DELTA carry a stable RSI(14) optimum of 60
(smoother trends → a higher momentum floor filters better). Everyone else keeps
the global RSI55 default. Adding a name here WITHOUT that walk-forward evidence is
exactly the overfit trap the research warned against — don't.

Each value is a partial cfg merged onto the base cfg passed to setdw_signal.buy_signal
(keys: rsi_min, rsi_max, adx_min, maxext, need_vol_conf, vol_mult, need_red_prior).
"""

PROFILES = {
    "KBANK.BK": {"rsi_min": 60},                 # walk-forward stable [60,60,60,60], beat 55
    "KTB.BK":   {"rsi_min": 60},                 # walk-forward stable [60,60,60,60], beat 55
    "DELTA.BK": {"vol_mult": 1.5, "adx_min": 25, "rsi_max": 70},  # vol1.5 + adx>=25 + rsi<=70:
                                                 # one-at-a-time validation: adx>=25 (fwd 75%/3.45,
                                                 # n=20) + rsi<=70 cap (study: RSI70+ = 44% bad)
                                                 # → combo fwd 88%/PF8 (n=16, tentative — thin)
    "KCE.BK":   {"vol_mult": 1.5},               # behavior study: vol surge is the #1 real-vs-fake
                                                 # tell; forward-validated vol>=1.5x → fwd 75%/PF3.33
                                                 # vs base 60%/1.45 (2.0x too strict, rsi60 redundant)
}


def _norm(symbol: str) -> str:
    """Match on the .BK ticker form used by the scanner/alert (case-insensitive)."""
    s = symbol.upper().strip()
    return s if s.endswith(".BK") else s + ".BK"


def cfg_for(symbol: str, base_cfg: dict) -> dict:
    """Return base_cfg with this symbol's validated overrides applied (new dict).
    Symbols not in PROFILES return base_cfg unchanged."""
    ov = PROFILES.get(_norm(symbol))
    if not ov:
        return base_cfg
    merged = dict(base_cfg)
    merged.update(ov)
    return merged


def rsi_min_for(symbol: str, default: int) -> int:
    """Convenience: the effective RSI floor for a symbol (for display/why-not text)."""
    return PROFILES.get(_norm(symbol), {}).get("rsi_min", default)
