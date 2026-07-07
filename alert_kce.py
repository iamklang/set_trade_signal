#!/usr/bin/env python3
"""
alert_kce.py — DEPRECATED shim. The alert is now watchlist-based in alert.py;
launchd points at alert.py. This shim keeps the old single-symbol entry working:
it just runs alert.py for KCE. Use `alert.py` (watchlist.txt / --symbols) instead.
"""
import sys

from alert import main

if __name__ == "__main__":
    # force the watchlist to KCE only, preserving the old behaviour
    sys.argv = [sys.argv[0], "--symbols", "KCE.BK"] + sys.argv[1:]
    sys.exit(main())
