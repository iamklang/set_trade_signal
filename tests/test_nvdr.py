"""Tests for the NVDR snapshot parser (set_data._parse_nvdr) — pure, no network."""
import set_data


SAMPLE = {
    "date": "2026-07-03T00:00:00+07:00",
    "nvdrTradings": [
        {"symbol": "KBANK", "buyVolume": 3_000_000, "sellVolume": 1_000_000,
         "netVolume": 2_000_000, "underlyingVolume": 10_000_000, "percentVolume": 40.0},
        {"symbol": "PTT", "buyVolume": 500_000, "sellVolume": 1_500_000,
         "netVolume": -1_000_000, "underlyingVolume": 5_000_000, "percentVolume": 40.0},
        {"symbol": "THIN", "buyVolume": 100, "sellVolume": None,
         "netVolume": 100, "underlyingVolume": None, "percentVolume": None},
    ],
}


def test_parse_date_and_symbols():
    date, snap = set_data._parse_nvdr(SAMPLE)
    assert date == "2026-07-03"
    assert set(snap) == {"KBANK.BK", "PTT.BK", "THIN.BK"}


def test_net_pct_sign_and_value():
    _, snap = set_data._parse_nvdr(SAMPLE)
    assert snap["KBANK.BK"]["net"] == 2_000_000
    assert snap["KBANK.BK"]["net_pct"] == 20.0        # 2M / 10M × 100, net BUY
    assert snap["PTT.BK"]["net_pct"] == -20.0         # net SELL -> negative pressure


def test_missing_underlying_gives_none_pct():
    _, snap = set_data._parse_nvdr(SAMPLE)
    assert snap["THIN.BK"]["net_pct"] is None
    assert snap["THIN.BK"]["net"] == 100


def test_bad_payload_is_empty():
    assert set_data._parse_nvdr(None) == (None, {})
    assert set_data._parse_nvdr({})[1] == {}
    assert set_data._parse_nvdr({"nvdrTradings": None})[1] == {}
