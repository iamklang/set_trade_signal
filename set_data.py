"""
set_data.py — read daily OHLCV from the SET (set.or.th) instead of Yahoo.

The public set.or.th API sits behind an Imperva/Incapsula WAF that 403s plain
HTTP clients (curl/requests). We therefore drive a headless Chromium via
Playwright: open the SET site once to clear the JS challenge (sets the
`incap_ses_*` / `visid_incap_*` cookies), then call the JSON chart API repeatedly
**in-page** (fetch) reusing that one session — so scanning 100 names is one
browser launch, not one per name.

Returns a DataFrame shaped exactly like yfinance auto_adjust output
(Open/High/Low/Close/Volume, DatetimeIndex) so setdw_signal.add_indicators works
unchanged.

    # many names, one browser, fetched concurrently:
    from set_data import fetch_all
    frames = fetch_all(["KCE.BK", "CCET.BK"], concurrency=6)   # {sym: df_or_None}

    # convenience one-shot (opens/closes a browser):
    from set_data import download
    df = download("KCE")

Fetching is async under the hood: one browser + one WAF session, then a
Semaphore-bounded asyncio.gather fetches up to `concurrency` symbols in parallel
(big wall-clock win vs the old one-at-a-time loop). Each symbol fetch retries with
backoff and re-warms the WAF on a 403; a symbol that still fails comes back as None
(callers treat it as missing) instead of aborting the whole batch. `cache_hours>0`
serves fresh `data/<SYM>.csv` without any network — only the uncached names are
fetched.

Notes / caveats (per the chosen "bypass WAF via browser" approach):
  - SLOW & FRAGILE: a browser launch + challenge takes a few seconds; the WAF can
    change and break this. A disk cache (data/<SYM>.csv) softens repeated runs.
  - Keep `concurrency` modest (default 6) — too many parallel hits from one IP can
    trip Incapsula rate-limiting; back off to 3–4 if it starts re-challenging.
  - SET symbols have NO ".BK" suffix — we strip it automatically.
  - EOD data: run after the 16:35 ICT close.
  - ACCURACY: only the most recent ~118 bars carry true OHLC (SET's cap); older
    warm-up bars are close-only with synthetic flat candles. Close-based signals
    (EMA20, SMA200, RSI) are exact; high/low-based ones (ADX, ATR, swing-low stop)
    are exact over the recent window but their Wilder seed is approximate — values
    can differ a little from a full-OHLC source. Gates (ADX>=20) are unaffected in
    practice; treat the printed ADX as indicative.
"""
import asyncio
import json
import os
import random
import time

import pandas as pd

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

SET_BASE = "https://www.set.or.th"
# A stock price page — loading it clears the Incapsula challenge for the API host.
WARMUP_URL = SET_BASE + "/en/market/product/stock/quote/{sym}/price"
# Two endpoints are merged because neither suffices alone:
#  - historical-trading: full daily OHLCV but capped at ~118 bars (~6 months).
#  - chart-quotation:     ~241 daily bars but CLOSE-only (no OHL).
# SMA200 needs ~200 closes, so we warm it from chart-quotation closes (synthetic
# flat OHLC on those older bars) and overlay the real OHLC for the recent ~118.
OHLC_URL = SET_BASE + "/api/set/stock/{sym}/historical-trading?period={period}"
CLOSE_URL = SET_BASE + "/api/set/stock/{sym}/chart-quotation?period={period}&accumulated=false"
# Fundamentals: per-fiscal-period financial ratios (roe/roa/margins/leverage). Returns the
# last ~4 annual rows (quarter "Q9" = full year) plus the latest quarter. Powers the composite
# QUALITY factor (SET q-factor / profitability — the ~2x-significant SET anomaly).
FUND_URL = SET_BASE + "/api/set/stock/{sym}/company-highlight/financial-data"
# NVDR (Thai-NVDR = the foreign-ownership proxy vehicle): per-stock net buy/sell for a single day.
# SET serves ONLY the latest session here (verified 2026-07-06 — no per-stock history endpoint
# exists), so it can't be backtested off the shelf; collect the daily snapshot forward to build a
# series. net_pct = net NVDR volume / underlying volume — the normalised foreign-proxy pressure.
NVDR_URL = SET_BASE + "/api/set/nvdr-trade/stock-trading?sortBy=symbol"
DEFAULT_PERIOD = "1Y"          # longest daily window SET serves on both endpoints
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _set_date(series):
    """Parse SET ISO timestamps to a tz-naive calendar date. SET stamps bars at
    midnight ICT (+07:00); converting to UTC would shift them to the prior day,
    so we read the date straight off the first 10 chars."""
    return pd.to_datetime(series.astype(str).str[:10])


def _norm(symbol: str) -> str:
    """KCE.BK -> KCE ; keep case as SET expects upper."""
    return symbol.upper().replace(".BK", "").strip()


def _df_ohlc(records) -> pd.DataFrame:
    """historical-trading array -> real OHLCV frame (recent ~118 bars)."""
    rows = []
    for q in records or []:
        ts, c = q.get("date"), q.get("close")
        if ts is None or c is None:
            continue
        rows.append((ts, q.get("open"), q.get("high"), q.get("low"), c,
                     q.get("totalVolume", q.get("volume"))))
    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df = pd.DataFrame(rows, columns=["ts", "Open", "High", "Low", "Close", "Volume"])
    df["ts"] = _set_date(df["ts"])
    return df.set_index("ts").sort_index()


def _df_close(records) -> pd.DataFrame:
    """chart-quotation array -> close/volume frame (~241 bars, no OHL)."""
    rows = []
    for q in records or []:
        ts = q.get("localDatetime") or q.get("datetime") or q.get("date")
        c = q.get("price", q.get("close"))
        if ts is None or c is None:
            continue
        rows.append((ts, c, q.get("volume", q.get("totalVolume"))))
    if not rows:
        return pd.DataFrame(columns=["Close", "Volume"])
    df = pd.DataFrame(rows, columns=["ts", "Close", "Volume"])
    df["ts"] = _set_date(df["ts"])
    return df.set_index("ts").sort_index()


def _merge(ohlc: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    """Build one yfinance-style OHLCV frame: real OHLC where historical-trading
    has it, synthetic flat OHLC (O=H=L=Close) on the older close-only bars so
    SMA200/EMA20 (close-based) warm up correctly."""
    if ohlc.empty and close.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    # union of dates; close series is the long backbone
    base = close.copy()
    if base.empty:
        base = ohlc[["Close", "Volume"]].copy()
    for col in ("Open", "High", "Low"):
        base[col] = base["Close"]          # synthetic flat candle on warm-up bars
    # overlay real OHLC (and its volume) on the recent bars
    if not ohlc.empty:
        base = base.reindex(base.index.union(ohlc.index))
        for col in ("Open", "High", "Low", "Close", "Volume"):
            base.loc[ohlc.index, col] = ohlc[col].values
        # any synthetic OHL still NaN (dates only in close) -> fill from Close
        for col in ("Open", "High", "Low"):
            base[col] = base[col].fillna(base["Close"])
    base = base.sort_index()
    base.index.name = "Date"
    for col in ("Open", "High", "Low"):     # guard against 0/NaN halted bars
        base[col] = pd.to_numeric(base[col], errors="coerce")
        base.loc[base[col].isna() | (base[col] <= 0), col] = base["Close"]
    base["Volume"] = pd.to_numeric(base["Volume"], errors="coerce").fillna(0)
    return base.dropna(subset=["Close"])[["Open", "High", "Low", "Close", "Volume"]].astype(float)


# ---------------------------------------------------------------------------
# cache helpers
# ---------------------------------------------------------------------------
def _cache_path(sym: str) -> str:
    return os.path.join(CACHE_DIR, f"{sym}.csv")


def _read_cache(sym: str, max_age_h: float):
    """Return a cached df if it exists and is within max_age_h, else None."""
    cpath = _cache_path(sym)
    if max_age_h and os.path.exists(cpath):
        age_h = (time.time() - os.path.getmtime(cpath)) / 3600
        if age_h <= max_age_h:
            return pd.read_csv(cpath, index_col=0, parse_dates=True)
    return None


def _write_cache(sym: str, df: pd.DataFrame):
    if not df.empty:
        os.makedirs(CACHE_DIR, exist_ok=True)
        df.to_csv(_cache_path(sym))


# ---------------------------------------------------------------------------
# async fetch core (one browser / one WAF session / bounded-concurrency gather)
# ---------------------------------------------------------------------------
_FETCH_JS = """async (u) => {
    const r = await fetch(u, {headers: {'accept': 'application/json'}});
    return {status: r.status, body: await r.text()};
}"""


async def _retry(make_coro, n, base_delay, label=""):
    """Await make_coro() up to n times with linear backoff + jitter."""
    last = None
    for i in range(n):
        try:
            return await make_coro()
        except Exception as e:  # noqa: BLE001 — surface the last error after retries
            last = e
            if i < n - 1:
                await asyncio.sleep(base_delay * (i + 1) + random.uniform(0, 0.4))
    raise last


async def _warm(page, warmup_sym):
    """Load a SET page so the Incapsula JS challenge sets the session cookies."""
    await page.goto(WARMUP_URL.format(sym=warmup_sym),
                    wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(2500)


async def _api(page, url, sym):
    res = await page.evaluate(_FETCH_JS, url)
    if res["status"] != 200:
        raise RuntimeError(f"SET API {sym} HTTP {res['status']}: {res['body'][:120]}")
    return json.loads(res["body"])


async def _fetch_symbol(ctx, sym, period, retries, warmup_sym):
    """Fetch + merge one symbol on its own page, retrying & re-warming on failure."""
    page = await ctx.new_page()
    try:
        async def grab():
            try:
                oh_raw = await _api(page, OHLC_URL.format(sym=sym, period=period), sym)
                cq_raw = await _api(page, CLOSE_URL.format(sym=sym, period=period), sym)
            except Exception:
                # the WAF challenge may have lapsed on this page — re-warm and retry once
                await _warm(page, warmup_sym)
                oh_raw = await _api(page, OHLC_URL.format(sym=sym, period=period), sym)
                cq_raw = await _api(page, CLOSE_URL.format(sym=sym, period=period), sym)
            return oh_raw, cq_raw

        oh_raw, cq_raw = await _retry(grab, retries, 0.8, sym)
        oh = oh_raw if isinstance(oh_raw, list) else (oh_raw.get("data") if isinstance(oh_raw, dict) else [])
        cq = cq_raw.get("quotations") if isinstance(cq_raw, dict) else cq_raw
        return _merge(_df_ohlc(oh), _df_close(cq))
    finally:
        await page.close()


async def _fetch_all_async(symbols, period, concurrency, cache_hours,
                           headless, warmup_sym, retries):
    out = {}                          # keyed by the ORIGINAL symbol as passed in
    to_fetch = []                     # [(original, normalized)]
    for s in symbols:
        cached = _read_cache(_norm(s), cache_hours)
        if cached is not None:
            out[s] = cached
        else:
            to_fetch.append((s, _norm(s)))
    if not to_fetch:
        return out

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        ctx = await browser.new_context(user_agent=UA, locale="en-US")
        try:
            warm_page = await ctx.new_page()
            await _retry(lambda: _warm(warm_page, warmup_sym), retries, 1.0, "warmup")
            await warm_page.close()

            sem = asyncio.Semaphore(max(1, concurrency))

            async def worker(orig, norm):
                async with sem:
                    await asyncio.sleep(random.uniform(0, 0.25))   # de-sync the launches
                    try:
                        df = await _fetch_symbol(ctx, norm, period, retries, warmup_sym)
                        _write_cache(norm, df)
                        return orig, df
                    except Exception as e:  # noqa: BLE001 — one bad name must not kill the batch
                        return orig, e

            results = await asyncio.gather(*(worker(o, n) for o, n in to_fetch))
        finally:
            await ctx.close()
            await browser.close()

    for orig, val in results:
        out[orig] = None if isinstance(val, Exception) else val
    return out


# ---------------------------------------------------------------------------
# sync entry points
# ---------------------------------------------------------------------------
def fetch_all(symbols, period: str = DEFAULT_PERIOD, concurrency: int = 6,
              cache_hours: float = 0, headless: bool = True,
              warmup_sym: str = "PTT", retries: int = 3) -> dict:
    """Fetch many symbols concurrently through one browser/WAF session.
    Returns {original_symbol: DataFrame or None}; None = fetch failed after retries."""
    return asyncio.run(_fetch_all_async(list(symbols), period, concurrency,
                                        cache_hours, headless, warmup_sym, retries))


def download(symbol: str, period: str = DEFAULT_PERIOD, headless: bool = True,
             cache_hours: float = 0) -> pd.DataFrame:
    """One-shot single symbol -> DataFrame (raises if the fetch failed)."""
    df = fetch_all([symbol], period=period, concurrency=1, cache_hours=cache_hours,
                   headless=headless).get(symbol)
    if df is None:
        raise RuntimeError(f"SET fetch failed for {symbol}")
    return df


# ---------------------------------------------------------------------------
# fundamentals (quality factor)
# ---------------------------------------------------------------------------
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _annual_roe_map(records):
    """financial-data array -> {fiscal_year: roe} using ANNUAL rows (quarter 'Q9') only.
    ROE is a percent (e.g. 12.7 = 12.7%). Empty dict if none parse."""
    out = {}
    for r in records or []:
        if str(r.get("quarter")) != "Q9":
            continue
        yr, roe = r.get("year"), _num(r.get("roe"))
        if yr is not None and roe is not None:
            out[int(yr)] = roe
    return out


def _latest_quality(records):
    """Most recent quality snapshot: prefer the latest ANNUAL (Q9) row, else the latest row.
    Returns {roe, roa, gpm, npm, year, quarter} or None."""
    if not records:
        return None
    annual = [r for r in records if str(r.get("quarter")) == "Q9"]
    pool = annual or records
    r = sorted(pool, key=lambda x: (x.get("year", 0), str(x.get("quarter"))))[-1]
    return {"roe": _num(r.get("roe")), "roa": _num(r.get("roa")),
            "gpm": _num(r.get("grossProfitMargin")), "npm": _num(r.get("netProfitMargin")),
            "year": r.get("year"), "quarter": r.get("quarter")}


async def _fetch_fund_async(symbols, concurrency, headless, warmup_sym, retries, history):
    """One browser/WAF session; fetch the financial-data endpoint per symbol concurrently.
    history=False -> {sym: latest-quality dict}; history=True -> {sym: {year: roe}}."""
    from playwright.async_api import async_playwright
    out = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        ctx = await browser.new_context(user_agent=UA, locale="en-US")
        try:
            wp = await ctx.new_page()
            await _retry(lambda: _warm(wp, warmup_sym), retries, 1.0, "warmup")
            await wp.close()
            sem = asyncio.Semaphore(max(1, concurrency))

            async def worker(orig, norm):
                async with sem:
                    await asyncio.sleep(random.uniform(0, 0.25))
                    page = await ctx.new_page()
                    try:
                        async def grab():
                            try:
                                return await _api(page, FUND_URL.format(sym=norm), norm)
                            except Exception:
                                await _warm(page, warmup_sym)
                                return await _api(page, FUND_URL.format(sym=norm), norm)
                        raw = await _retry(grab, retries, 0.8, norm)
                        recs = raw if isinstance(raw, list) else (
                            raw.get("data") if isinstance(raw, dict) else [])
                        return orig, (_annual_roe_map(recs) if history else _latest_quality(recs))
                    except Exception:
                        return orig, None
                    finally:
                        await page.close()

            res = await asyncio.gather(*(worker(s, _norm(s)) for s in symbols))
        finally:
            await ctx.close()
            await browser.close()
    for orig, val in res:
        out[orig] = val
    return out


def _parse_nvdr(payload):
    """SET nvdr-trade payload -> (date_str, {SYMBOL.BK: {net, net_pct}}). net = NVDR net volume
    (buy-sell); net_pct = net / underlying volume × 100 = the foreign-proxy net pressure on a name
    that day (positive = NVDR net buying). Pure/testable — no network."""
    if not isinstance(payload, dict):
        return None, {}
    date = str(payload.get("date", ""))[:10]
    out = {}
    for r in payload.get("nvdrTradings", []) or []:
        sym = r.get("symbol")
        if not sym:
            continue
        net = _num(r.get("netVolume")) or 0.0
        uv = _num(r.get("underlyingVolume"))
        out[str(sym) + ".BK"] = {"net": net,
                                 "net_pct": (net / uv * 100) if uv else None}
    return date, out


async def _fetch_nvdr_async(headless, warmup_sym, retries):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        ctx = await browser.new_context(user_agent=UA, locale="en-US")
        try:
            page = await ctx.new_page()
            await _retry(lambda: _warm(page, warmup_sym), retries, 1.0, "warmup")

            async def grab():
                try:
                    return await _api(page, NVDR_URL, "nvdr")
                except Exception:
                    await _warm(page, warmup_sym)
                    return await _api(page, NVDR_URL, "nvdr")

            return _parse_nvdr(await _retry(grab, retries, 0.8, "nvdr"))
        finally:
            await ctx.close()
            await browser.close()


def fetch_nvdr(headless: bool = True, warmup_sym: str = "KBANK", retries: int = 3):
    """Latest daily per-stock NVDR (foreign-proxy) snapshot from the SET, via the same Playwright/
    WAF session as the rest of set_data. Returns (date_str, {SYMBOL.BK: {net, net_pct}}). ⚠️ SET
    serves ONLY the latest session — no history — so this is a LIVE context signal; run the daily
    collector (collect_nvdr.py) to accumulate a backtestable series over time."""
    return asyncio.run(_fetch_nvdr_async(headless, warmup_sym, retries))


def fetch_yahoo_all(tickers, period: str = "2y") -> dict:
    """Batch daily OHLCV for many .BK tickers via yfinance in ONE call — no browser, no WAF
    (Yahoo also posts the SET EOD bar same-evening, ahead of the SET overnight batch, and
    carries real OHLC on every bar). Returns {ticker: DataFrame or None}, yfinance-style."""
    import yfinance as yf
    tickers = list(tickers)
    out = {}
    if not tickers:
        return out
    df = yf.download(tickers, period=period, interval="1d", progress=False,
                     auto_adjust=True, group_by="ticker", threads=True)
    single = len(tickers) == 1
    for t in tickers:
        try:
            d = df if single else df[t]
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(-1)
            d = d.dropna(how="all")
            out[t] = d if len(d) else None
        except Exception:
            out[t] = None
    return out


def fetch_fundamentals(symbols, concurrency: int = 6, headless: bool = True,
                       warmup_sym: str = "PTT", retries: int = 3, history: bool = False) -> dict:
    """Fetch SET financial ratios concurrently through one browser/WAF session.
    history=False -> {sym: {roe,roa,gpm,npm,year,quarter} or None} (latest snapshot).
    history=True  -> {sym: {fiscal_year: roe}} (annual ROE panel, for backtests)."""
    return asyncio.run(_fetch_fund_async(list(symbols), concurrency, headless,
                                         warmup_sym, retries, history))


if __name__ == "__main__":
    import sys
    syms = sys.argv[1:] or ["KCE"]
    for sym, df in fetch_all(syms).items():
        if df is None or df.empty:
            print(f"{sym}: FETCH FAILED"); continue
        print(f"{sym}: {len(df)} bars, {df.index.min().date()}..{df.index.max().date()}")
        print(df.tail(3).round(2).to_string())
