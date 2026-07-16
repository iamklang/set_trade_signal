"""market.py — market profile: route state files, universe, and cost model per market.

The system was built for the SET; this lets the SAME code run a second, fully separate
book for US (S&P 500) equities without forking any logic.

Default market is **SET** (`TR_MARKET` unset or "set") → state lives in the repo root,
byte-identical to the original layout. `TR_MARKET=us` → state lives under `us/`, with the
US universe + US cost model. Scanners accept `--market us`, which just sets the env var
early in main() before any state path is resolved.

Resolution is done at CALL time (not import time) so the market can be selected in main()
regardless of import order.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

_PROFILES = {
    "set": {
        "state_dir": HERE,                                   # repo root — unchanged
        "universe": os.path.join(HERE, "set100.bk.txt"),
        "watchlist": os.path.join(HERE, "watchlist.txt"),
        "cost_mode": "set",
        "currency": "฿",
        "equity": 100_000,
        "lot": 100,                                          # SET board lot
        "label": "SET",
        "tag": "SET DW",                                     # brief header prefix
    },
    "us": {
        "state_dir": os.path.join(HERE, "us"),
        "universe": os.path.join(HERE, "us", "us500.txt"),
        "watchlist": os.path.join(HERE, "us", "watchlist.txt"),
        "cost_mode": "us",
        "currency": "$",
        "equity": 30_000,
        "lot": 1,                                            # US trades in single shares
        "label": "US",
        "tag": "US S&P500",                                  # brief header prefix
    },
}


def current():
    """Active market key ('set' default). Read from the TR_MARKET env var."""
    return (os.environ.get("TR_MARKET") or "set").lower().strip() or "set"


def set_market(name):
    """Select the market (call early in main() from a --market arg). No-op if falsy."""
    if name:
        os.environ["TR_MARKET"] = str(name).lower().strip()


def profile(market=None):
    return _PROFILES.get((market or current()), _PROFILES["set"])


def state_dir(market=None):
    """Directory holding this market's state (positions/quarter/regime/rank/scans).
    Created on demand. For SET this is the repo root (already exists)."""
    d = profile(market)["state_dir"]
    os.makedirs(d, exist_ok=True)
    return d


def state_path(filename, market=None):
    """Absolute path to a per-market state file, e.g. state_path('positions.json')."""
    return os.path.join(state_dir(market), filename)


def scans_dir(market=None):
    """Per-market dated-scan output dir (<state_dir>/scans), created on demand."""
    d = os.path.join(state_dir(market), "scans")
    os.makedirs(d, exist_ok=True)
    return d


def universe_path(market=None):
    return profile(market)["universe"]


def watchlist_path(market=None):
    return profile(market)["watchlist"]


def cost_mode(market=None):
    return profile(market)["cost_mode"]


def currency(market=None):
    return profile(market)["currency"]


def default_equity(market=None):
    return profile(market)["equity"]


def lot(market=None):
    """Board-lot size for share rounding (SET=100, US=1)."""
    return profile(market)["lot"]


def tag(market=None):
    """Brief-header prefix for the analytical LINE/console briefs (e.g. 'SET DW', 'US S&P500')."""
    return profile(market)["tag"]
