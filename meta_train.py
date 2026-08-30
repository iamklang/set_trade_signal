"""meta_train.py — Phase 2 of /quant-meta-label: train the secondary + HONEST validation.

Consumes the dataset from meta_label.build_dataset and answers the only question
that matters: does gating the primary triggers on a secondary probability beat
"take every trigger" — NET of cost, on PURGED cross-validation, after the
Deflated Sharpe penalty for the thresholds we searched? If not, the honest
output is FALL BACK TO PRIMARY (Fix 2).

Zero external ML deps (numpy + pandas only) so it runs in the project venv:
  • WeightedLogit      — L2 logistic regression, sample-weighted, NaN-imputing
                         (small & shallow = Fix 1; swap in a GBM later if desired)
  • purged_folds       — López de Prado purged + embargoed CV (no label leakage)
  • probabilistic /    — Bailey-López de Prado PSR & DSR (norm cdf/ppf w/o scipy)
    deflated_sharpe
  • mda_importance     — permutation (Mean-Decrease-Accuracy) importance, not MDI

Everything here is gated by /quant-validation. A US dataset is trained/validated
separately (Fix 4); pooling needs the `market` dummy AND a generalization check.

Usage:
  python meta_train.py --data reports/meta_dataset_set.csv --cost 0.006
"""
import math

import numpy as np
import pandas as pd

import meta_label as ml

GAMMA = 0.5772156649015329          # Euler-Mascheroni
FEATURES = ml.FEATURES              # same feature contract as Phase 1


# --------------------------------------------------------------------------- #
# Normal CDF / PPF without scipy
# --------------------------------------------------------------------------- #
def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p):
    """Inverse standard-normal CDF (Acklam's rational approximation, ~1e-9)."""
    if not (0.0 < p < 1.0):
        return -math.inf if p <= 0 else math.inf
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p <= phigh:
        q = p - 0.5
        r = q*q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
            ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


# --------------------------------------------------------------------------- #
# Sharpe, PSR, DSR (per-trade series; not annualized)
# --------------------------------------------------------------------------- #
def sharpe(returns):
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 3 or r.std(ddof=1) == 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1))


def _moments(returns):
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    sr = sharpe(r)
    m = r.mean()
    s = r.std(ddof=1)
    skew = float(((r - m) ** 3).mean() / s ** 3) if s > 0 else 0.0
    kurt = float(((r - m) ** 4).mean() / s ** 4) if s > 0 else 3.0   # non-excess
    return sr, skew, kurt, n


def w_moments(returns, weights):
    """Uniqueness-WEIGHTED (sr, skew, kurt, n_eff). n_eff is Kish's effective sample
    size (Σw)²/Σw² — the honest count once overlapping labels are down-weighted.
    Using weighted moments end-to-end keeps Sharpe, expectancy and DSR consistent."""
    r = np.asarray(returns, dtype=float)
    w = np.asarray(weights, dtype=float)
    m = np.isfinite(r) & np.isfinite(w) & (w > 0)
    r, w = r[m], w[m]
    if len(r) < 3 or w.sum() <= 0:
        return float("nan"), 0.0, 3.0, 0.0
    mu = np.average(r, weights=w)
    var = np.average((r - mu) ** 2, weights=w)
    sd = math.sqrt(var) if var > 0 else 0.0
    if sd == 0:
        return float("nan"), 0.0, 3.0, 0.0
    skew = float(np.average((r - mu) ** 3, weights=w) / sd ** 3)
    kurt = float(np.average((r - mu) ** 4, weights=w) / sd ** 4)     # non-excess
    n_eff = float(w.sum() ** 2 / np.square(w).sum())
    return float(mu / sd), skew, kurt, n_eff


def wsharpe(returns, weights):
    return w_moments(returns, weights)[0]


def deflated_sharpe_weighted(returns, weights, n_trials, sr_variance):
    """DSR on uniqueness-weighted returns (weighted Sharpe + Kish n_eff)."""
    sr, skew, kurt, n_eff = w_moments(returns, weights)
    sr0 = expected_max_sharpe(sr_variance, n_trials)
    return probabilistic_sharpe_ratio(sr, sr0, n_eff, skew, kurt), sr, sr0, n_eff


def probabilistic_sharpe_ratio(sr, sr_star, n, skew, kurt):
    """PSR: P(true SR > sr_star) given observed sr, length n, skew, (non-excess) kurt."""
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4.0 * sr * sr))
    return _norm_cdf((sr - sr_star) * math.sqrt(max(1, n - 1)) / denom)


def expected_max_sharpe(sr_variance, n_trials):
    """Expected maximum Sharpe under n_trials independent trials (Bailey-LdP)."""
    if n_trials < 2 or sr_variance <= 0:
        return 0.0
    e = math.e
    return math.sqrt(sr_variance) * (
        (1 - GAMMA) * _norm_ppf(1 - 1.0 / n_trials)
        + GAMMA * _norm_ppf(1 - 1.0 / (n_trials * e)))


def deflated_sharpe_ratio(returns, n_trials, sr_variance):
    """DSR = PSR(SR0) where SR0 = expected max Sharpe over n_trials. >0.95 = survives."""
    sr, skew, kurt, n = _moments(returns)
    sr0 = expected_max_sharpe(sr_variance, n_trials)
    return probabilistic_sharpe_ratio(sr, sr0, n, skew, kurt), sr, sr0


# --------------------------------------------------------------------------- #
# AUC (rank-based, no sklearn)
# --------------------------------------------------------------------------- #
def _rankdata(a):
    a = np.asarray(a, dtype=float)
    order = a.argsort()
    ranks = np.empty(len(a), dtype=float)
    ranks[order] = np.arange(1, len(a) + 1)
    # average ties
    _, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    sums = np.zeros(len(counts))
    np.add.at(sums, inv, ranks)
    return sums[inv] / counts[inv]


def auc(y, p):
    y = np.asarray(y); p = np.asarray(p, dtype=float)
    ok = np.isfinite(p)
    y, p = y[ok], p[ok]
    npos, nneg = int((y == 1).sum()), int((y == 0).sum())
    if npos == 0 or nneg == 0:
        return float("nan")
    r = _rankdata(p)
    return float((r[y == 1].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


# --------------------------------------------------------------------------- #
# WeightedLogit — L2 logistic regression, sample-weighted, NaN-imputing
# --------------------------------------------------------------------------- #
class WeightedLogit:
    def __init__(self, l2=1.0, lr=0.5, epochs=800):
        self.l2, self.lr, self.epochs = l2, lr, epochs

    def _prep(self, X):
        X = np.asarray(X, dtype=float).copy()
        idx = np.where(~np.isfinite(X))
        if len(idx[0]):
            X[idx] = np.take(self.mu_, idx[1])          # mean-impute (train mean)
        return (X - self.mu_) / self.sd_

    def fit(self, X, y, w=None):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        self.mu_ = np.nanmean(X, axis=0)
        self.mu_ = np.where(np.isfinite(self.mu_), self.mu_, 0.0)
        sd = np.nanstd(X, axis=0)
        self.sd_ = np.where((sd > 0) & np.isfinite(sd), sd, 1.0)
        Xs = self._prep(X)
        n, d = Xs.shape
        w = np.ones(n) if w is None else np.asarray(w, dtype=float)
        w = w * (n / w.sum()) if w.sum() else np.ones(n)   # normalize to mean 1
        self.coef_ = np.zeros(d)
        self.b_ = 0.0
        for _ in range(self.epochs):
            z = Xs @ self.coef_ + self.b_
            p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
            g = (p - y) * w
            self.coef_ -= self.lr * (Xs.T @ g / n + self.l2 * self.coef_ / n)
            self.b_ -= self.lr * (g.mean())
        return self

    def predict_proba(self, X):
        z = self._prep(X) @ self.coef_ + self.b_
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


# --------------------------------------------------------------------------- #
# Purged + embargoed CV (López de Prado, AFML Ch.7)
# --------------------------------------------------------------------------- #
def purged_folds(dates, exit_dates, k=5, embargo_days=20):
    """Yield (train_pos, test_pos) integer-index arrays.

    Test folds are k contiguous blocks in DATE order. A training sample is kept
    only if its label span [date, exit_date] does NOT overlap the test block's
    time range, with an extra `embargo_days` buffer on the right — so a 20-day
    label can never straddle the train/test boundary and leak.
    """
    dates = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    exits = pd.to_datetime(pd.Series(exit_dates).reset_index(drop=True))
    n = len(dates)
    order = np.argsort(dates.values)
    emb = pd.Timedelta(days=embargo_days)
    for block in np.array_split(order, k):
        if len(block) == 0:
            continue
        t_start = dates.iloc[block].min()
        t_end = exits.iloc[block].max()
        keep = (exits.values < np.datetime64(t_start)) | \
               (dates.values > np.datetime64(t_end + emb))
        train = np.where(keep)[0]
        yield train, np.asarray(block)


# --------------------------------------------------------------------------- #
# Cross-validated out-of-fold probabilities + MDA importance
# --------------------------------------------------------------------------- #
def cv_oof(df, features=FEATURES, k=5, embargo_days=20, model_factory=None, seed=0):
    """Purged-CV out-of-fold P(win) for every row, plus per-fold test AUC and
    permutation (MDA) importance averaged over folds."""
    model_factory = model_factory or (lambda: WeightedLogit())
    X = df[features].to_numpy(dtype=float)
    y = df["label"].to_numpy(dtype=float)
    w = df["weight"].to_numpy(dtype=float) if "weight" in df else None
    oof = np.full(len(df), np.nan)
    aucs, mda = [], {f: [] for f in features}
    rng = np.random.default_rng(seed)
    for train, test in purged_folds(df["date"], df["exit_date"], k, embargo_days):
        if len(train) < 20 or len(test) == 0:
            continue
        m = model_factory().fit(X[train], y[train], None if w is None else w[train])
        p = m.predict_proba(X[test])
        oof[test] = p
        base = auc(y[test], p)
        aucs.append(base)
        if np.isfinite(base):
            for j, f in enumerate(features):        # MDA: permute one feature, watch AUC fall
                Xp = X[test].copy()
                Xp[:, j] = rng.permutation(Xp[:, j])
                mda[f].append(base - auc(y[test], m.predict_proba(Xp)))
    imp = {f: float(np.nanmean(v)) if v else float("nan") for f, v in mda.items()}
    return oof, {"fold_auc": aucs, "mean_auc": float(np.nanmean(aucs)) if aucs else float("nan"),
                 "mda": dict(sorted(imp.items(), key=lambda kv: -(kv[1] if np.isfinite(kv[1]) else -9)))}


# --------------------------------------------------------------------------- #
# Honest evaluation: baseline vs gated, net of cost, DSR-penalized
# --------------------------------------------------------------------------- #
def net_R(df, cost_roundtrip=0.006):
    """Per-trade R net of a flat round-trip cost. cost in R = cost_frac / (riskU/close).
    riskU_pct is (riskU/close)*100, so cost_R = cost_roundtrip / (riskU_pct/100)."""
    r = df["ret_R"].to_numpy(dtype=float)
    rp = df["riskU_pct"].to_numpy(dtype=float) / 100.0
    cost_R = np.where(rp > 0, cost_roundtrip / rp, 0.0)
    return r - cost_R


def _wavg(v, w):
    """Weighted mean that ignores non-finite values/weights (else one NaN poisons it)."""
    v = np.asarray(v, dtype=float)
    w = np.asarray(w, dtype=float)
    m = np.isfinite(v) & np.isfinite(w)
    return float(np.average(v[m], weights=w[m])) if m.any() and w[m].sum() > 0 else float("nan")


def evaluate(df, oof, cost_roundtrip=0.006, thresholds=None):
    """Compare 'take every trigger' vs gating on oof P(win) at each threshold.
    DSR penalizes for the number of thresholds searched (n_trials)."""
    nr = net_R(df, cost_roundtrip)
    w = df["weight"].to_numpy(dtype=float)
    y = df["label"].to_numpy(dtype=float)
    base = {"name": "primary-only (all triggers)", "n": int(len(df)),
            "coverage": 1.0, "precision": float(y.mean()),
            "exp_R": _wavg(nr, w), "sharpe": wsharpe(nr, w)}
    if thresholds is None:
        thresholds = [round(t, 2) for t in np.quantile(oof[np.isfinite(oof)], [.3, .4, .5, .6, .7])]
    trials = []
    for thr in thresholds:
        acc = np.isfinite(oof) & (oof >= thr)
        if acc.sum() < 20:
            continue
        trials.append({"name": f"gated p>={thr}", "thr": thr, "n": int(acc.sum()),
                       "coverage": float(acc.mean()), "precision": float(y[acc].mean()),
                       "exp_R": _wavg(nr[acc], w[acc]),
                       "sharpe": wsharpe(nr[acc], w[acc])})
    if not trials:
        return {"baseline": base, "best": None, "dsr": None, "trials": [],
                "verdict": "FALL BACK TO PRIMARY (no usable threshold)"}
    sr_var = float(np.var([t["sharpe"] for t in trials], ddof=1)) if len(trials) > 1 else 0.0
    best = max(trials, key=lambda t: (t["sharpe"] if np.isfinite(t["sharpe"]) else -9))
    acc = np.isfinite(oof) & (oof >= best["thr"])
    dsr, sr, sr0, n_eff = deflated_sharpe_weighted(nr[acc], w[acc],
                                                   n_trials=max(2, len(trials)),
                                                   sr_variance=max(sr_var, 1e-6))
    # A deployable secondary must beat primary on BOTH weighted expectancy AND
    # weighted Sharpe, clear DSR>0.95, AND leave positive net expectancy — a lower
    # negative expectancy is not an edge, just a smaller loss.
    beats = (best["sharpe"] > base["sharpe"]) and (best["exp_R"] > base["exp_R"]) \
        and (dsr > 0.95) and (best["exp_R"] > 0)
    verdict = ("DEPLOY candidate (clear /quant-validation Gate 5 on SET/DW next)"
               if beats else "FALL BACK TO PRIMARY (secondary adds no DSR-robust edge)")
    return {"baseline": base, "best": best, "trials": trials,
            "dsr": {"DSR": round(dsr, 4), "SR": round(sr, 4), "SR0_expected_max": round(sr0, 4),
                    "n_trials": max(2, len(trials)), "n_eff": round(n_eff, 1)},
            "verdict": verdict}


def train_and_validate(df, cost_roundtrip=0.006, k=5, embargo_days=20, model_factory=None):
    oof, cv = cv_oof(df, k=k, embargo_days=embargo_days, model_factory=model_factory)
    ev = evaluate(df, oof, cost_roundtrip)
    return {"summary": ml.summary(df), "cv": cv, "eval": ev, "oof": oof}


def _print_report(rep):
    s, cv, ev = rep["summary"], rep["cv"], rep["eval"]
    print("=" * 68)
    print("META-LABEL Phase 2 — purged-CV validation")
    print("=" * 68)
    print(f"dataset: rows={s['rows']} eff_N={s['eff_n']} win={s['win']} "
          f"exp_R={s.get('exp_R')}  [{s['start'][:10]} .. {s['end'][:10]}]")
    print(f"CV mean test AUC: {cv['mean_auc']:.4f}  (0.5=no skill)  folds={len(cv['fold_auc'])}")
    print("top MDA features (AUC drop when permuted):")
    for f, v in list(cv["mda"].items())[:6]:
        print(f"    {f:12s} {v:+.4f}")
    b, best = ev["baseline"], ev["best"]
    print("-" * 68)
    print(f"{'sleeve':32s} {'n':>6s} {'cov':>6s} {'prec':>6s} {'expR':>7s} {'Sharpe':>7s}")
    print(f"{b['name']:32s} {b['n']:>6d} {b['coverage']:>6.2f} {b['precision']:>6.3f} "
          f"{b['exp_R']:>7.3f} {b['sharpe']:>7.3f}")
    for t in ev["trials"]:
        mark = " *" if best and t is best else ""
        print(f"{t['name']:32s} {t['n']:>6d} {t['coverage']:>6.2f} {t['precision']:>6.3f} "
              f"{t['exp_R']:>7.3f} {t['sharpe']:>7.3f}{mark}")
    if ev["dsr"]:
        d = ev["dsr"]
        print("-" * 68)
        print(f"Deflated Sharpe (best gate): DSR={d['DSR']}  wSR={d['SR']}  "
              f"E[maxSR|{d['n_trials']} trials]={d['SR0_expected_max']}  n_eff={d['n_eff']}"
              f"   (survives if DSR>0.95)")
    print("=" * 68)
    print("VERDICT:", ev["verdict"])
    print("=" * 68)


def main(argv=None):                               # pragma: no cover - CLI glue
    import argparse
    ap = argparse.ArgumentParser(description="Phase 2: train + purged-CV validate the secondary.")
    ap.add_argument("--data", required=True, help="CSV from meta_label.build_dataset")
    ap.add_argument("--cost", type=float, default=0.006, help="flat round-trip cost fraction (0.006 = 0.6 pct)")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--embargo", type=int, default=20)
    ap.add_argument("--l2", type=float, default=1.0)
    a = ap.parse_args(argv)
    df = pd.read_csv(a.data, parse_dates=["date", "exit_date"])
    rep = train_and_validate(df, cost_roundtrip=a.cost, k=a.folds, embargo_days=a.embargo,
                             model_factory=lambda: WeightedLogit(l2=a.l2))
    _print_report(rep)
    return rep


if __name__ == "__main__":                         # pragma: no cover
    main()
