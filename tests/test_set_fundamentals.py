"""Tests for set_data fundamentals parsing (quality factor source)."""
import set_data


RECS = [
    {"quarter": "Q9", "year": 2023, "roe": 10.0, "roa": 7.0,
     "grossProfitMargin": 20.0, "netProfitMargin": 5.0},
    {"quarter": "Q9", "year": 2024, "roe": 12.5, "roa": 8.0,
     "grossProfitMargin": 22.0, "netProfitMargin": 6.0},
    {"quarter": "Q1", "year": 2025, "roe": 3.1, "roa": 2.0,
     "grossProfitMargin": 21.0, "netProfitMargin": 5.5},
]


def test_annual_roe_map_uses_only_annual_rows():
    m = set_data._annual_roe_map(RECS)
    assert m == {2023: 10.0, 2024: 12.5}      # the Q1 quarter row is excluded


def test_annual_roe_map_empty():
    assert set_data._annual_roe_map([]) == {}
    assert set_data._annual_roe_map([{"quarter": "Q1", "year": 2025, "roe": 3.0}]) == {}


def test_latest_quality_prefers_latest_annual():
    q = set_data._latest_quality(RECS)
    assert q["year"] == 2024 and q["roe"] == 12.5     # latest Q9, not the newer Q1
    assert q["gpm"] == 22.0 and q["npm"] == 6.0


def test_latest_quality_falls_back_to_any_when_no_annual():
    q = set_data._latest_quality([{"quarter": "Q1", "year": 2025, "roe": 3.1}])
    assert q["year"] == 2025 and q["roe"] == 3.1


def test_latest_quality_none_on_empty():
    assert set_data._latest_quality([]) is None


def test_num_coercion():
    assert set_data._num("12.5") == 12.5
    assert set_data._num(None) is None
    assert set_data._num("n/a") is None
