"""Tests for line_notify.py (spec 003-line-notify)."""
import json
import os
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

import pytest

import line_notify


class TestSendLinePush:
    """T002-T004: unit tests for send_line_push."""

    @patch.dict(os.environ, {"LINE_CHANNEL_TOKEN": "tok123", "LINE_GROUP_ID": "uid456"})
    @patch("line_notify.urlopen")
    def test_sends_correct_request(self, mock_urlopen):
        """T002/AC-1: correct HTTP request format."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = line_notify.send_line_push("hello")

        assert result is True
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://api.line.me/v2/bot/message/push"
        assert req.get_header("Authorization") == "Bearer tok123"
        assert req.get_header("Content-type") == "application/json"
        body = json.loads(req.data)
        assert body["to"] == "uid456"
        assert body["messages"] == [{"type": "text", "text": "hello"}]

    @patch.dict(os.environ, {"LINE_CHANNEL_TOKEN": "tok123", "LINE_GROUP_ID": "uid456"})
    @patch("line_notify.urlopen")
    def test_returns_false_on_http_error(self, mock_urlopen):
        """T003/AC-3: return False + log on API error."""
        mock_urlopen.side_effect = HTTPError(
            url="https://api.line.me/v2/bot/message/push",
            code=401, msg="Unauthorized", hdrs={}, fp=None,
        )

        result = line_notify.send_line_push("hello")

        assert result is False

    @patch.dict(os.environ, {}, clear=True)
    def test_skip_when_no_env_vars(self):
        """T004/AC-4: skip silently when env vars not set."""
        result = line_notify.send_line_push("hello")
        assert result is False

    @patch.dict(os.environ, {"LINE_CHANNEL_TOKEN": "tok123"}, clear=True)
    def test_skip_when_partial_env_vars(self):
        """T004: skip when only token set but no user ID."""
        result = line_notify.send_line_push("hello")
        assert result is False


class TestFormatAlertMessage:
    """T005: message formatting for alert integration."""

    def test_format_with_signals(self):
        """AC-1: message includes ticker details in table format."""
        fired = [
            ("KCE.BK", {"close": 55.0, "stop": 52.5, "t1": 58.0, "t2": 61.0,
                         "size": 1900, "rsi": 62, "adx": 30, "distPct": -1.2}),
            ("DELTA.BK", {"close": 320.0, "stop": 310.0, "t1": 340.0, "t2": 360.0,
                          "size": 300, "rsi": 55, "adx": 28, "distPct": -0.8}),
        ]
        msg = line_notify.format_alert_message(fired, scan_date="2026-06-26")
        assert "2 BUY(dip)" in msg
        assert "2026-06-26" in msg
        assert "Ticker" in msg
        assert "---" in msg
        assert "KCE" in msg
        assert "DELTA" in msg
        assert "55.00" in msg
        assert "52.50" in msg

    def test_column_order_matches_scan_dip_rsi_adx_buy_stop(self):
        """Layout mirrors scan_dip.py's console table: RSI, ADX, buy, stop (buy sits right
        after ADX, before stop) — not just that the values are present, but in that order."""
        fired = [("KCE.BK", {"close": 55.0, "buy": 55.0, "stop": 52.5, "t1": 58.0, "t2": 61.0,
                             "size": 1900, "rsi": 62, "adx": 30, "distPct": -1.2})]
        msg = line_notify.format_alert_message(fired)
        hdr_line = next(l for l in msg.splitlines() if "RSI" in l)
        assert (hdr_line.index("RSI") < hdr_line.index("ADX")
                < hdr_line.index("Buy") < hdr_line.index("Stop"))
        row_line = next(l for l in msg.splitlines() if "KCE" in l)
        assert "62" in row_line and "30" in row_line     # RSI/ADX values rendered

    def test_size_tilt_legend_shown(self):
        fired = [("KCE.BK", {"close": 55.0, "stop": 52.5, "t1": 58.0, "t2": 61.0,
                             "size": 2850, "size_mult": 1.5, "rsi": 62, "adx": 30,
                             "distPct": -1.2, "quintile": 1})]
        msg = line_notify.format_alert_message(fired)
        assert "Size ปรับตาม quintile" in msg
        assert "2,850" in msg          # tilted size shown

    def test_no_size_tilt_legend_when_neutral(self):
        fired = [("KCE.BK", {"close": 55.0, "stop": 52.5, "t1": 58.0, "t2": 61.0,
                             "size": 1900, "size_mult": 1.0, "rsi": 62, "adx": 30,
                             "distPct": -1.2})]
        msg = line_notify.format_alert_message(fired)
        assert "Size ปรับตาม quintile" not in msg

    def test_format_no_signals(self):
        """AC-2: message says no signals with date."""
        msg = line_notify.format_alert_message([], scan_date="2026-06-26")
        assert "ไม่มี" in msg
        assert "2026-06-26" in msg


class TestValidatedSection:
    """Validated-candidates digest (live still-holdable check) from earlier scans."""

    VALID = [
        {"ticker": "AOT.BK", "scan_date": "2026-06-25", "close": 61.5,
         "cur": 63.25, "pl_pct": 2.85, "status": "HOLD"},
        {"ticker": "PSL.BK", "scan_date": "2026-05-29", "close": 7.65,
         "cur": 7.10, "pl_pct": -7.19, "status": "WEAK"},
    ]

    def test_section_appended_when_no_fresh_signals(self):
        msg = line_notify.format_alert_message([], scan_date="2026-06-29",
                                               validated=self.VALID)
        assert "ไม่มีสัญญาณ" in msg          # fresh part unchanged
        assert "ผ่าน validate (2)" in msg     # digest header with count
        assert "AOT" in msg and "PSL" in msg
        assert "HOLD" in msg and "WEAK" in msg  # live status shown
        assert "61.50" in msg and "63.25" in msg  # entry + now
        assert "+2.9%" in msg and "-7.2%" in msg  # signed P/L

    def test_section_appended_after_fresh_signals(self):
        fired = [("KCE.BK", {"close": 55.0, "stop": 52.5, "t1": 58.0, "t2": 61.0,
                             "size": 1900, "rsi": 62, "adx": 30, "distPct": -1.2})]
        msg = line_notify.format_alert_message(fired, validated=self.VALID)
        assert "1 BUY(dip)" in msg            # fresh table present
        assert "ผ่าน validate (2)" in msg     # and digest below it

    def test_no_section_when_empty(self):
        msg = line_notify.format_alert_message([], validated=[])
        assert "ผ่าน validate" not in msg

    def test_leader_star_marks_q1(self):
        """quintile==1 names get a ★ prefix + the leader legend; non-Q1 do not."""
        validated = [
            {"ticker": "AOT.BK", "close": 61.5, "cur": 63.0, "pl_pct": 2.4,
             "status": "HOLD", "quintile": 1},
            {"ticker": "ERW.BK", "close": 3.06, "cur": 3.04, "pl_pct": -0.7,
             "status": "WEAK", "quintile": 2},
        ]
        msg = line_notify.format_alert_message([], validated=validated)
        assert "★AOT" in msg          # Q1 leader marked
        assert "★ERW" not in msg      # Q2 not marked
        assert "ผู้นำ composite Q1" in msg   # legend present

    def test_leader_star_on_fired(self):
        fired = [("KCE.BK", {"close": 55.0, "stop": 52.5, "t1": 58.0, "t2": 61.0,
                             "size": 1900, "rsi": 62, "adx": 30, "distPct": -1.2,
                             "quintile": 1})]
        msg = line_notify.format_alert_message(fired)
        assert "★KCE" in msg
        assert "ผู้นำ composite Q1" in msg


class TestPositionsSection:
    """format_positions_section / format_alert_message with the let-winners-run watchlist."""

    HOLD = [{"ticker": "AOT.BK", "entry_close": 61.5, "cur": 63.25, "pl_pct": 2.85,
             "status": "RUN", "new": False},
            {"ticker": "KCE.BK", "entry_close": 55.0, "cur": 55.0, "pl_pct": 0.0,
             "status": "HOLD", "new": True}]
    SELL = [{"ticker": "PSL.BK", "entry_close": 7.65, "cur": 7.10, "pl_pct": -7.19,
             "status": "STOP", "sell_reason": "STOP"}]
    T1 = [{"ticker": "SCGP.BK", "entry_close": 26.5, "cur": 28.6, "pl_pct": 7.9,
           "status": "RUN"}]

    def test_sell_and_hold_blocks(self):
        s = line_notify.format_positions_section(self.HOLD, self.SELL)
        assert "ขาย (1)" in s and "PSL" in s
        assert "หลุดสต็อป — ขายทั้งหมด" in s    # STOP note
        assert "ถืออยู่ (2)" in s and "AOT" in s and "KCE" in s
        assert "61.50" in s and "63.25" in s          # entry + now
        assert "+2.9%" in s and "-7.2%" in s          # signed P/L
        assert "•" in s                                # new-entry marker on KCE

    def test_t1_block(self):
        s = line_notify.format_positions_section(self.HOLD, [], self.T1)
        assert "ถึง T1 (1)" in s and "SCGP" in s
        assert "เลื่อน stop → ทุน" in s and "ปล่อยวิ่ง" in s

    def test_holding_shows_entry_date_stop_target(self):
        """Wide holdings table carries the trigger date + stop + T1 target."""
        hold = [{"ticker": "KCE.BK", "entry_date": "2026-07-14", "entry_close": 45.0,
                 "cur": 44.25, "pl_pct": -1.7, "status": "HOLD", "stop": 36.25,
                 "t1": 53.75, "t2": 58.12}]
        s = line_notify.format_positions_section(hold, [])
        assert "14/07" in s                       # entry date (DD/MM)
        assert "45.00" in s and "44.25" in s      # entry + now
        assert "36.25" in s and "53.75" in s      # stop + T1
        assert "Date" in s and "Stop" in s and "T1" in s   # column headers

    def test_sell_shows_entry_date_and_levels(self):
        """Sell rows carry entry date, stop and target detail."""
        sell = [{"ticker": "ADVANC.BK", "entry_date": "2026-07-14", "entry_close": 382.0,
                 "cur": 375.0, "pl_pct": -1.8, "status": "ROTATE", "sell_reason": "ROTATE",
                 "stop": 362.0, "t1": 402.0}]
        s = line_notify.format_positions_section([], sell)
        assert "14/07" in s and "382.00" in s and "362.00" in s and "402.00" in s

    def test_trail_sell_note(self):
        sell = [{"ticker": "SCGP.BK", "entry_close": 26.5, "cur": 29.6, "pl_pct": 11.7,
                 "status": "TRAIL", "sell_reason": "TRAIL"}]
        s = line_notify.format_positions_section([], sell)
        assert "หลุด EMA20" in s and "ขายเก็บกำไร" in s

    def test_rotate_sell_note(self):
        sell = [{"ticker": "QH.BK", "entry_close": 1.38, "cur": 1.40, "pl_pct": 1.4,
                 "status": "ROTATE", "sell_reason": "ROTATE"}]
        s = line_notify.format_positions_section([], sell)
        assert "สับเปลี่ยน" in s

    def test_empty_returns_blank(self):
        assert line_notify.format_positions_section([], [], []) == ""

    def test_alert_message_prefers_positions(self):
        msg = line_notify.format_alert_message([], scan_date="2026-07-03",
                                               holding=self.HOLD, sell_today=self.SELL,
                                               t1_today=self.T1)
        assert "ไม่มีสัญญาณ" in msg                    # fresh part unchanged
        assert "ถืออยู่ (2)" in msg and "ขาย (1)" in msg and "ถึง T1 (1)" in msg

    def test_q1_star_in_positions(self):
        hold = [{"ticker": "AOT.BK", "entry_close": 61.5, "cur": 63.0, "pl_pct": 2.4,
                 "status": "RUN", "quintile": 1}]
        s = line_notify.format_positions_section(hold, [])
        assert "★AOT" in s and "ผู้นำ composite Q1" in s


class TestBullMessage:
    """format_bull_message — the bullish-scan shortlist + auto analysis."""

    SHORT = [
        {"ticker": "CCET.BK", "signals": ["reclaim", "trend"], "close": 9.0,
         "distPct": 1.7, "rsi": 54, "adx": 30, "buy": 9.0, "stop": 8.5, "t1": 9.5,
         "size": 5000},                                 # tight + strong ADX -> low-risk
        {"ticker": "TFG.BK", "signals": ["dip", "breakout", "trend"], "close": 11.0,
         "distPct": 15.5, "rsi": 74, "adx": 21, "buy": 11.0, "stop": 9.5, "t1": 12.5,
         "size": 6800},                                 # extended >10%
    ]
    TALLY = {"dip": 4, "breakout": 7, "reclaim": 2, "golden": 0, "trend": 50}

    def test_breadth_and_shortlist(self):
        msg = line_notify.format_bull_message(self.SHORT, 100, 50, self.TALLY, "2026-06-30")
        assert "50/100 ขาขึ้น" in msg and "บูลกว้าง" in msg
        assert "★ Q1 leader + trigger (2)" in msg
        assert "CCET" in msg and "TFG" in msg
        assert "rcl" in msg and "dip+brk" in msg      # trigger abbreviations

    def test_shortlist_shows_buy_order_ticket(self):
        msg = line_notify.format_bull_message(self.SHORT, 100, 50, self.TALLY, "2026-06-30")
        assert "Buy" in msg and "Stop" in msg          # order-ticket columns present
        assert "Buy=ราคา limit วันถัดไป" in msg         # the next-day buy-price note
        assert "9.00" in msg and "8.50" in msg          # CCET buy + stop
        assert "5,000" in msg and "6,800" in msg        # tilted sizes

    def test_auto_analysis_flags(self):
        msg = line_notify.format_bull_message(self.SHORT, 100, 50, self.TALLY, "2026-06-30")
        assert "เข้าง่าย/เสี่ยงต่ำ" in msg and "CCET" in msg
        assert "ระวังยืด" in msg and "TFG*" in msg      # extended marked with *

    def test_empty_shortlist(self):
        msg = line_notify.format_bull_message([], 100, 12, {"trend": 12}, "2026-06-30")
        assert "ไม่มี Q1 leader" in msg
        assert "12/100" in msg

    def test_missing_values_render_dash(self):
        validated = [{"ticker": "X.BK", "scan_date": "2026-06-01",
                      "close": None, "cur": None, "pl_pct": None}]
        msg = line_notify.format_alert_message([], validated=validated)
        assert "?" in msg                     # status falls back to '?'
        assert "-" in msg                     # _fmt_num/_fmt_pct fall back to '-'
