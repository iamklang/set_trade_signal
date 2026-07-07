"""Tests for viewer.py scan sort order (spec 002-sort-by-date)."""
import os
import textwrap
from unittest.mock import patch

import pytest

from viewer import _load_scans, HERE


@pytest.fixture()
def scan_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("viewer.HERE", tmp_path)
    return tmp_path


def _write_csv(directory, filename, tickers=("TEST.BK",)):
    rows = "\n".join(
        f"{t},10.0,-1.0,40,25,9.5,11.0,12.0,100,,," for t in tickers
    )
    header = "ticker,close,distPct,rsi,adx,stop,t1,t2,size,validated,validate_reason,validated_at"
    (directory / filename).write_text(f"{header}\n{rows}\n")


def test_ac1_sorted_by_scan_date_desc(scan_dir):
    """AC-1: scans for 06-24, 06-25, 06-26 → returned as 06-26, 06-25, 06-24."""
    _write_csv(scan_dir, "dip_scan_2026-06-24.csv")
    _write_csv(scan_dir, "dip_scan_2026-06-25.csv")
    _write_csv(scan_dir, "dip_scan_2026-06-26.csv")

    scans = _load_scans()
    dates = [s["scan_date"] for s in scans]
    assert dates == ["2026-06-26", "2026-06-25", "2026-06-24"]


def test_ac2_same_date_sorted_by_run_time_desc(scan_dir):
    """AC-2: two scans with same scan_date → newer run_time first."""
    _write_csv(scan_dir, "dip_scan_2026-06-26_20260629_204425.csv")
    _write_csv(scan_dir, "dip_scan_2026-06-26_20260629_205812.csv")

    scans = _load_scans()
    assert len(scans) == 2
    assert scans[0]["run_time"] > scans[1]["run_time"]
    assert scans[0]["scan_date"] == scans[1]["scan_date"] == "2026-06-26"


def test_ac3_scan_date_beats_run_time(scan_dir):
    """AC-3: scan_date 06-27 (run 06-28) before scan_date 06-26 (run 06-29)."""
    _write_csv(scan_dir, "dip_scan_2026-06-26_20260629_120000.csv")
    _write_csv(scan_dir, "dip_scan_2026-06-27_20260628_120000.csv")

    scans = _load_scans()
    assert scans[0]["scan_date"] == "2026-06-27"
    assert scans[1]["scan_date"] == "2026-06-26"
