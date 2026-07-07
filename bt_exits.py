#!/usr/bin/env python3
"""
bt_exits.py — trade-level backtest comparing SELL-RULE variants for the managed
BUY(dip) watchlist, to find which exit maximises profit.

Entry (all variants): setdw_signal.buy_signal on a closed bar, enter at that close,
5-bar cooldown. Stop = structural swing-low (llStop). risk=entry-stop, T1=+1R, T2=+1.5R.

Variants differ only in the EXIT:
  V0_current   STOP | T2 | WEAK(close<EMA20 OR close<entry)   <- positions.py TODAY
  V1_stop_t2   STOP | T2                                       (let the stop do the work)
  V2_ema_only  STOP | T2 | close<EMA20   (drop the below-entry early-bail)
  V3_scaleout  50% at T1 -> breakeven stop -> rest T2/BE       (.pine documented default)
  V4_trail_t1  STOP | T2 | (after T1 touched) close<EMA20      (run till 1R locked)

Each also run with a composite Q1-leaders entry filter (mom+trend, monthly).
Cost 0.30%/side. Yahoo SET100, N years. NOT advice — mechanics only.
"""
import sys
import numpy as np
import pandas as pd

HERE = "/Users/klang/Git/trading_dr"
sys.path.insert(0, HERE)
import setdw_signal as sig       # noqa: E402
import composite                 # noqa: E402
import set_data                  # noqa: E402

YEARS = 10
COST = 0.003                     # per side
COOLDOWN = 5
RR1, RR2 = 1.0, 1.5


def load_universe(path):
    with open(path) as f:
        return [t.split("#")[0].strip() for t in f if t.split("#")[0].strip()]


def prep(df):
    df = sig.add_indicators(df)
    cfg = {"rsi_min": sig.RSI_MIN, "adx_min": sig.ADX_MIN, "need_vol_conf": True}
    df["buy"] = sig.buy_signal(df, cfg)
    return df


def sim_trade(df, i, variant):
    """Simulate one trade opened on bar i (enter at close). Return (ret_frac, bars, reason)."""
    o = df["Open"].values; h = df["High"].values; l = df["Low"].values
    c = df["Close"].values; ema = df["ema"].values
    entry = c[i]
    stop = df["llStop"].values[i]
    if not (entry > stop > 0):
        return None
    risk = entry - stop
    t1, t2 = entry + RR1 * risk, entry + RR2 * risk
    n = len(df)
    scaled = False           # V3: has the T1 half been sold?
    part_ret = 0.0           # realised return from the T1 half (weighted 0.5)
    cur_stop = stop
    t1_hit = False           # V4
    for j in range(i + 1, n):
        # ---- stop (worst-case first); gap-through fills at the open ----
        if l[j] <= cur_stop:
            fill = min(o[j], cur_stop)
            r = (fill - entry) / entry
            if variant == "V3_scaleout" and scaled:
                return (part_ret + 0.5 * r, j - i, "STOP2")
            return (r, j - i, "STOP")
        # ---- targets ----
        if variant == "V3_scaleout":
            if not scaled and h[j] >= t1:
                fill1 = max(o[j], t1)
                part_ret = 0.5 * (fill1 - entry) / entry
                scaled = True
                cur_stop = entry            # move remainder to breakeven
            if scaled and h[j] >= t2:
                fill2 = max(o[j], t2)
                return (part_ret + 0.5 * (fill2 - entry) / entry, j - i, "T2")
        elif variant == "V5_run":
            # let the winner run: lock breakeven at T1, then trail on EMA, NO T2 cap
            if not t1_hit and h[j] >= t1:
                t1_hit = True
                cur_stop = entry
            if t1_hit and c[j] < ema[j]:
                return ((c[j] - entry) / entry, j - i, "RUN")
        else:
            if h[j] >= t2:
                fill = max(o[j], t2)
                return ((fill - entry) / entry, j - i, "T2")
            if variant == "V4_trail_t1" and h[j] >= t1:
                t1_hit = True
            # ---- close-based (trend) exits ----
            if variant == "V0_current" and (c[j] < ema[j] or c[j] < entry):
                return ((c[j] - entry) / entry, j - i, "WEAK")
            if variant == "V2_ema_only" and c[j] < ema[j]:
                return ((c[j] - entry) / entry, j - i, "EMA")
            if variant == "V4_trail_t1" and t1_hit and c[j] < ema[j]:
                return ((c[j] - entry) / entry, j - i, "TRAIL")
    # ran out of data -> close at last bar
    r = (c[-1] - entry) / entry
    if variant == "V3_scaleout" and scaled:
        return (part_ret + 0.5 * r, n - 1 - i, "EOD")
    return (r, n - 1 - i, "EOD")


def run(frames, variant, q1map=None):
    """Walk every name, collect net-of-cost trade returns. q1map: {month_ts: set(Q1)} filter."""
    rets, bars, reasons = [], [], {}
    legs = 2 if variant == "V3_scaleout" else 2   # round trip both legs -> 2*COST either way
    for t, df in frames.items():
        buy = df["buy"].values
        idx = df.index
        i = 0; n = len(df)
        last_exit = -10_000
        while i < n:
            if buy[i] and (i - last_exit) >= COOLDOWN:
                if q1map is not None:
                    # most-recent month-end Q1 set as of this bar
                    ms = [m for m in q1map if m <= idx[i]]
                    if not ms or t not in q1map[max(ms)]:
                        i += 1; continue
                res = sim_trade(df, i, variant)
                if res is None:
                    i += 1; continue
                r, held, reason = res
                r -= legs * COST                    # round-trip cost
                rets.append(r); bars.append(held)
                reasons[reason] = reasons.get(reason, 0) + 1
                last_exit = i + held
                i = last_exit + 1
            else:
                i += 1
    return np.array(rets), np.array(bars), reasons


def stats(rets):
    if len(rets) == 0:
        return None
    wins = rets[rets > 0]; losses = rets[rets < 0]
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else np.inf
    return {
        "n": len(rets), "win%": (rets > 0).mean() * 100,
        "avg%": rets.mean() * 100, "med%": np.median(rets) * 100,
        "PF": pf, "sum%": rets.sum() * 100, "exp%": rets.mean() * 100,
    }


def q1_monthly(frames):
    """{month_end_ts: set(Q1 tickers)} using mom+trend composite."""
    px = pd.DataFrame({t: df["Close"] for t, df in frames.items()}).sort_index()
    out = {}
    for d in px.resample("ME").last().index:
        R = composite.cross_section_scores(frames, asof=d, weights={"mom": 1, "trend": 1, "lowvol": 0})
        if not R.empty:
            out[d] = set(R[R["quintile"] == 1].index)
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=YEARS)
    ap.add_argument("--universe", default=f"{HERE}/set100.bk.txt")
    ap.add_argument("--q1", action="store_true", help="also run each variant Q1-leaders-only")
    a = ap.parse_args()

    tickers = load_universe(a.universe)
    print(f"fetching {len(tickers)} names, {a.years}y Yahoo ...")
    raw = set_data.fetch_yahoo_all(tickers, period=f"{a.years}y")
    frames = {}
    for t, df in raw.items():
        if df is None or len(df) < sig.SMA_LEN + 60:
            continue
        frames[t] = prep(df)
    print(f"usable: {len(frames)} names\n")

    variants = ["V0_current", "V1_stop_t2", "V2_ema_only", "V3_scaleout",
                "V4_trail_t1", "V5_run"]
    hdr = f"{'variant':<14}{'n':>6}{'win%':>7}{'avg%':>7}{'med%':>7}{'PF':>6}{'sum%':>9}{'~hold':>7}"

    def table(title, q1map):
        print(title); print(hdr); print("-" * len(hdr))
        best = None
        for v in variants:
            rets, bars, reasons = run(frames, v, q1map)
            s = stats(rets)
            if s is None:
                print(f"{v:<14}  (no trades)"); continue
            hold = int(np.median(bars)) if len(bars) else 0
            print(f"{v:<14}{s['n']:>6}{s['win%']:>7.1f}{s['avg%']:>7.2f}{s['med%']:>7.2f}"
                  f"{s['PF']:>6.2f}{s['sum%']:>9.0f}{hold:>7}")
            top = ", ".join(f"{k}:{n}" for k, n in sorted(reasons.items(), key=lambda x: -x[1]))
            print(f"{'':14}exits: {top}")
            if best is None or s["PF"] > best[1]:
                best = (v, s["PF"], s["exp%"])
        print(f"\n  >>> best PF: {best[0]} (PF {best[1]:.2f}, expectancy {best[2]:+.2f}%/trade)\n")

    table("=== ALL dip entries (no ranking filter) ===", None)

    if a.q1:
        print("computing monthly composite Q1 (mom+trend) ...")
        q1map = q1_monthly(frames)
        table("=== Q1-leaders-only entries (composite mom+trend) ===", q1map)


if __name__ == "__main__":
    main()
