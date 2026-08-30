"""Tests for meta_train.py — Phase 2 validation primitives (offline, numpy-only)."""
import numpy as np
import pandas as pd

import meta_train as mt


# ---------------- normal cdf/ppf ----------------

def test_norm_ppf_cdf_roundtrip():
    for p in (0.01, 0.25, 0.5, 0.84134, 0.99):
        assert abs(mt._norm_cdf(mt._norm_ppf(p)) - p) < 1e-4


# ---------------- Sharpe / PSR / DSR ----------------

def test_sharpe_basic():
    r = np.array([0.01, 0.02, -0.005, 0.015, 0.0])
    assert abs(mt.sharpe(r) - (r.mean() / r.std(ddof=1))) < 1e-9


def test_psr_monotonic_in_sr():
    # higher observed SR -> higher probability of beating the benchmark
    lo = mt.probabilistic_sharpe_ratio(0.10, 0.0, 200, 0.0, 3.0)
    hi = mt.probabilistic_sharpe_ratio(0.30, 0.0, 200, 0.0, 3.0)
    assert 0.0 <= lo < hi <= 1.0


def test_expected_max_sharpe_grows_with_trials():
    e10 = mt.expected_max_sharpe(0.04, 10)
    e100 = mt.expected_max_sharpe(0.04, 100)
    assert e100 > e10 > 0


def test_deflated_sharpe_penalizes_trials():
    rng = np.random.default_rng(1)
    r = rng.normal(0.05, 1.0, 500)              # small positive edge
    dsr_few, _, sr0_few = mt.deflated_sharpe_ratio(r, n_trials=2, sr_variance=0.02)
    dsr_many, _, sr0_many = mt.deflated_sharpe_ratio(r, n_trials=200, sr_variance=0.02)
    assert sr0_many > sr0_few                    # more trials -> higher bar
    assert dsr_many < dsr_few                    # -> lower deflated confidence


# ---------------- AUC ----------------

def test_auc_perfect_and_random():
    y = np.array([0, 0, 1, 1])
    assert mt.auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert mt.auc(y, np.array([0.9, 0.8, 0.2, 0.1])) == 0.0
    assert abs(mt.auc(y, np.array([0.5, 0.5, 0.5, 0.5])) - 0.5) < 1e-9


# ---------------- WeightedLogit ----------------

def test_logit_learns_separable():
    rng = np.random.default_rng(0)
    n = 200
    x = np.concatenate([rng.normal(-2, 1, n), rng.normal(2, 1, n)]).reshape(-1, 1)
    y = np.concatenate([np.zeros(n), np.ones(n)])
    m = mt.WeightedLogit(l2=0.01).fit(x, y)
    p = m.predict_proba(x)
    assert mt.auc(y, p) > 0.95


def test_logit_imputes_nan():
    rng = np.random.default_rng(2)
    x = rng.normal(0, 1, (50, 2))
    y = (x[:, 0] > 0).astype(float)
    m = mt.WeightedLogit().fit(x, y)
    p = m.predict_proba(np.array([[np.nan, np.nan]]))   # must not crash / nan-out
    assert np.isfinite(p[0])


# ---------------- purged_folds: no leakage ----------------

def test_purged_folds_no_overlap_with_test_range():
    n = 100
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    exits = dates + pd.Timedelta(days=20)          # 20-day labels overlap heavily
    df = pd.DataFrame({"date": dates, "exit_date": exits})
    for train, test in mt.purged_folds(df["date"], df["exit_date"], k=5, embargo_days=20):
        t_start = df["date"].iloc[test].min()
        t_end = df["exit_date"].iloc[test].max() + pd.Timedelta(days=20)
        for j in train:                             # every train span must miss [t_start, t_end]
            d, e = df["date"].iloc[j], df["exit_date"].iloc[j]
            assert e < t_start or d > t_end


def test_wsharpe_matches_population_moments_when_equal_weights():
    # weighted moments use population variance (÷N); with equal weights wSharpe
    # equals mean/std(ddof=0). (Unweighted sharpe() uses ddof=1, ~0.2% apart.)
    rng = np.random.default_rng(3)
    r = rng.normal(0.05, 1.0, 300)
    w = np.ones(300)
    assert abs(mt.wsharpe(r, w) - r.mean() / r.std(ddof=0)) < 1e-9
    assert abs(mt.wsharpe(r, w) - mt.sharpe(r)) < 1e-2      # ddof-only gap


def test_w_moments_neff_is_kish():
    r = np.array([1.0, -1.0, 0.5, -0.5])
    w = np.array([1.0, 1.0, 0.5, 0.5])
    _, _, _, n_eff = mt.w_moments(r, w)
    assert abs(n_eff - (w.sum() ** 2 / (w ** 2).sum())) < 1e-9


def test_wsharpe_downweights_clustered_trades():
    # two independent losers (w=1) + many overlapping winners (w small):
    # weighted Sharpe must be worse than the naive unweighted one
    r = np.array([-1.0, -1.0] + [1.0] * 8)
    w = np.array([1.0, 1.0] + [0.1] * 8)
    assert mt.wsharpe(r, w) < mt.sharpe(r)


def test_net_R_subtracts_cost():
    df = pd.DataFrame({"ret_R": [1.0, -1.0], "riskU_pct": [5.0, 5.0]})
    nr = mt.net_R(df, cost_roundtrip=0.006)
    # cost_R = 0.006 / 0.05 = 0.12
    assert abs(nr[0] - (1.0 - 0.12)) < 1e-9
    assert abs(nr[1] - (-1.0 - 0.12)) < 1e-9
