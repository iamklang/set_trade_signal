"""
housekeeping.py — keep the log / scan-artifact directories from growing unbounded.

The daily jobs append one file per run/date forever (logs/alert_*.log, dip_scan_*.csv,
bull_scan_*.csv). `retain_newest` keeps the N most-recent matches of a glob and deletes the
rest — called at the tail of each script so cleanup rides along with normal runs.
"""
import glob
import os


def retain_newest(pattern: str, keep: int) -> int:
    """Delete all but the `keep` newest (by mtime) files matching `pattern`.
    Returns the number removed. `keep<=0` is a no-op (never mass-delete by accident)."""
    if keep <= 0:
        return 0
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    removed = 0
    for f in files[keep:]:
        try:
            os.remove(f)
            removed += 1
        except OSError:
            pass
    return removed
