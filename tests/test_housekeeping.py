"""Tests for housekeeping.retain_newest."""
import os
import time

import housekeeping


def _touch(path, mtime):
    path.write_text("x")
    os.utime(path, (mtime, mtime))


def test_keeps_newest_deletes_rest(tmp_path):
    now = 1_700_000_000
    for i in range(6):
        _touch(tmp_path / f"alert_{i}.log", now + i)      # i=5 newest
    removed = housekeeping.retain_newest(str(tmp_path / "alert_*.log"), keep=3)
    assert removed == 3
    left = sorted(p.name for p in tmp_path.glob("alert_*.log"))
    assert left == ["alert_3.log", "alert_4.log", "alert_5.log"]


def test_keep_zero_is_noop(tmp_path):
    _touch(tmp_path / "a_1.csv", 1_700_000_000)
    assert housekeeping.retain_newest(str(tmp_path / "a_*.csv"), keep=0) == 0
    assert (tmp_path / "a_1.csv").exists()


def test_fewer_than_keep_removes_nothing(tmp_path):
    for i in range(2):
        _touch(tmp_path / f"b_{i}.csv", 1_700_000_000 + i)
    assert housekeeping.retain_newest(str(tmp_path / "b_*.csv"), keep=5) == 0
    assert len(list(tmp_path.glob("b_*.csv"))) == 2
