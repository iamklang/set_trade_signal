"""
line_notify.py — LINE Messaging API push helper.

Sends a plain-text push message to a LINE group via the LINE Messaging API.
Credentials are read from environment variables:
  LINE_CHANNEL_TOKEN  — channel access token (long-lived)
  LINE_GROUP_ID       — target group ID

Best-effort: returns False on any error without raising.
"""
import json
import os
from urllib.request import Request, urlopen
from urllib.error import URLError

LINE_API_URL = "https://api.line.me/v2/bot/message/push"


def send_line_push(text: str) -> bool:
    token = os.environ.get("LINE_CHANNEL_TOKEN", "")
    group_id = os.environ.get("LINE_GROUP_ID", "")
    if not token or not group_id:
        return False

    body = json.dumps({
        "to": group_id,
        "messages": [{"type": "text", "text": text[:5000]}],
    }).encode()

    req = Request(LINE_API_URL, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    })

    try:
        with urlopen(req) as resp:
            return resp.status == 200
    except (URLError, OSError) as e:
        print(f"  [LINE] send failed: {e}")
        return False


def _fmt_num(x, width=8):
    """Right-align a number as 2dp, or '-' when missing/non-numeric."""
    try:
        return f"{float(x):>{width}.2f}"
    except (TypeError, ValueError):
        return f"{'-':>{width}}"


def _fmt_pct(x, width=6):
    """Signed 1dp percent (e.g. '+2.8%'), or '-' when missing/non-numeric."""
    try:
        return f"{float(x):+.1f}%".rjust(width)
    except (TypeError, ValueError):
        return "-".rjust(width)


def _disp_name(ticker, quintile=None):
    """Ticker sans .BK, prefixed with ★ when it's a top-quintile composite leader (Q1)."""
    base = str(ticker).replace(".BK", "")
    return ("★" + base) if quintile == 1 else base


def _fmt_date(d):
    """Compact 'DD/MM' from an ISO 'YYYY-MM-DD' entry date, or '-' when missing."""
    s = str(d or "")
    parts = s.split("-")
    if len(parts) == 3:
        return f"{parts[2]}/{parts[1]}"
    return "-"


def _format_validated_section(validated: list[dict]) -> str:
    """Render the 'prior-scan hits — still holdable?' block. Each item:
    {ticker, close (=entry), and optionally cur, pl_pct, status, quintile}. `status` is
    the live verdict on the latest bar (HOLD/WEAK/STOP/T1/T2/?); `quintile`==1 marks a
    composite trend leader (★). Returns '' when empty."""
    if not validated:
        return ""
    names = [_disp_name(v["ticker"], v.get("quintile")) for v in validated]
    w = max([len(n) for n in names] + [6])
    hdr = f"{'Ticker':<{w}}  {'Stat':<4}  {'Entry':>7}  {'Now':>7}  {'P/L':>6}"
    sep = "-" * len(hdr)
    lines = [f"ผ่าน validate ({len(validated)}) — ถือได้ไหม ณ ล่าสุด:\n", hdr, sep]
    for v, name in zip(validated, names):
        st = (v.get("status") or "?")[:4]
        lines.append(f"{name:<{w}}  {st:<4}  {_fmt_num(v.get('close'), 7)}"
                     f"  {_fmt_num(v.get('cur'), 7)}  {_fmt_pct(v.get('pl_pct'))}")
    lines.append("\nHOLD=เหนือ EMA20+เหนือทุน  WEAK=หลุด EMA20/ต่ำกว่าทุน  "
                 "STOP=หลุดสต็อป  T1/T2=ถึงเป้า")
    if any(v.get("quintile") == 1 for v in validated):
        lines.append("★=ผู้นำ composite Q1 (mom+trend)")
    return "\n".join(lines)


_SELL_NOTE = {
    "TRAIL": "หลุด EMA20 (หลัง T1) — ขายเก็บกำไร",
    "STOP": "หลุดสต็อป — ขายทั้งหมด",
    "BE": "กลับมาที่ทุน — ขาย เสมอตัว",
    "ROTATE": "สับเปลี่ยนออก — ตัวใหม่มี upside ดีกว่า",
}


def format_positions_section(holding: list[dict] | None,
                             sell_today: list[dict] | None,
                             t1_today: list[dict] | None = None,
                             capital_info: dict | None = None) -> str:
    """Render the stateful let-winners-run managed watchlist (positions.json) for the LINE
    brief: a SELL-today block (fully exited — trail/stop/breakeven/rotate), a T1 block (stop
    moved to breakeven, now running), then current holdings with live status/P-L. Each row:
    {ticker, entry_close, cur, pl_pct, status, sell_reason?, new?, quintile?}. '' when empty."""
    holding = holding or []
    sell_today = sell_today or []
    t1_today = t1_today or []
    if not holding and not sell_today and not t1_today:
        return ""
    blocks = []
    if sell_today:
        lines = [f"🔴 ขาย ({len(sell_today)}):"]
        for r in sell_today:
            name = _disp_name(r.get("ticker"), r.get("quintile"))
            note = _SELL_NOTE.get(r.get("sell_reason"), "ขาย")
            if r.get("sell_reason") == "ROTATE" and r.get("rotate_for"):
                nm_new = r["rotate_for"].replace(".BK", "")
                diff = (r.get("opp_diff") or 0) * 100
                note = f"สับเปลี่ยน → เข้า {nm_new} (upside ดีกว่า {diff:.0f}%)"
            lines.append(f"  {name} {r.get('sell_reason','?')}  {_fmt_pct(r.get('pl_pct')).strip()}")
            lines.append(f"    เข้า {_fmt_date(r.get('entry_date'))} @{_fmt_num(r.get('entry_close'), 0).strip()}"
                         f" → ล่าสุด {_fmt_num(r.get('cur'), 0).strip()}"
                         f" · 🛑 {_fmt_num(r.get('stop'), 0).strip()}"
                         f" · 🎯 T1 {_fmt_num(r.get('t1'), 0).strip()}")
            lines.append(f"    {note}")
        blocks.append("\n".join(lines))
    if t1_today:
        lines = [f"🔵 ถึง T1 ({len(t1_today)}):"]
        for r in t1_today:
            name = _disp_name(r.get("ticker"), r.get("quintile"))
            lines.append(f"  {name}  {_fmt_pct(r.get('pl_pct')).strip()}")
            lines.append(f"    เข้า {_fmt_date(r.get('entry_date'))} @{_fmt_num(r.get('entry_close'), 0).strip()}"
                         f" → ล่าสุด {_fmt_num(r.get('cur'), 0).strip()}"
                         f" · เลื่อน stop → ทุน ({_fmt_num(r.get('entry_close'), 0).strip()})"
                         f" · 🎯 T2 {_fmt_num(r.get('t2'), 0).strip()} ปล่อยวิ่ง")
        blocks.append("\n".join(lines))
    if holding:
        names = [_disp_name(r.get("ticker"), r.get("quintile")) for r in holding]
        w = max([len(n) for n in names] + [6])
        hdr = (f"{'Ticker':<{w}}  {'Stat':<4}  {'Date':<5}  {'Entry':>7}  {'Now':>7}"
               f"  {'Stop':>7}  {'T1':>7}  {'P/L':>6}")
        lines = [f"📈 ถืออยู่ ({len(holding)}):\n", hdr, "-" * len(hdr)]
        for r, name in zip(holding, names):
            st = (r.get("status") or "?")[:4]
            mark = "•" if r.get("new") else ""
            lines.append(f"{name:<{w}}  {st:<4}  {_fmt_date(r.get('entry_date')):<5}"
                         f"  {_fmt_num(r.get('entry_close'), 7)}  {_fmt_num(r.get('cur'), 7)}"
                         f"  {_fmt_num(r.get('stop'), 7)}  {_fmt_num(r.get('t1'), 7)}"
                         f"  {_fmt_pct(r.get('pl_pct'))}{mark}")
        lines.append("\nStat: HOLD=ถือเต็ม(ก่อน T1) · RUN=ล็อกทุนแล้ว ปล่อยวิ่ง")
        lines.append("Date=วันเข้าซื้อ · Stop=จุดขายตัดขาดทุน · T1=เป้าแรก(+1R)")
        lines.append("ขายเมื่อ: หลุด Stop / หลุด EMA20(หลัง T1) · •=เข้าใหม่วันนี้")
        if any(r.get("quintile") == 1 for r in holding):
            lines.append("★=ผู้นำ composite Q1 (mom+trend)")
        blocks.append("\n".join(lines))
    if capital_info:
        blocks.append(f"💰 ทุน: ฿{capital_info['equity']:,.0f} | "
                      f"ใช้ไป ฿{capital_info['committed']:,.0f} | "
                      f"เหลือ ฿{capital_info['available']:,.0f} "
                      f"({capital_info.get('pct_available', 0):.0f}%)")
    return "\n\n".join(blocks)


def format_alert_message(fired: list[tuple[str, dict]], scan_date: str = "",
                         validated: list[dict] | None = None,
                         holding: list[dict] | None = None,
                         sell_today: list[dict] | None = None,
                         t1_today: list[dict] | None = None,
                         capital_info: dict | None = None) -> str:
    header = "SET DW Swing Alert"
    if scan_date:
        header += f" ({scan_date})"

    if fired:
        names = [_disp_name(s, p.get("quintile")) for s, p in fired]
        w = max([len(n) for n in names] + [6])
        # Column order mirrors scan_dip.py's table: ticker, RSI, ADX, buy, stop, T1, T2, size
        # (buy sits right after ADX, before stop — same layout as the scanner's own console table).
        hdr = (f"{'Ticker':<{w}}  {'RSI':>4}  {'ADX':>4}  {'Buy':>8}  {'Stop':>8}"
               f"  {'T1':>8}  {'T2':>8}  {'Size':>8}")
        sep = "-" * len(hdr)
        lines = [f"{header}\n", f"{len(fired)} BUY(dip) signals (buy=ราคา limit วันถัดไป):\n",
                 hdr, sep]
        for (sym, p), name in zip(fired, names):
            lines.append(
                f"{name:<{w}}  {p['rsi']:>4.0f}  {p['adx']:>4.0f}"
                f"  {p.get('buy', p['close']):>8.2f}  {p['stop']:>8.2f}"
                f"  {p['t1']:>8.2f}  {p['t2']:>8.2f}  {p['size']:>8,}"
            )
        if any(p.get("quintile") == 1 for _, p in fired):
            lines.append("\n★=ผู้นำ composite Q1 (mom+trend)")
        if any((p.get("size_mult") or 1) != 1 for _, p in fired):
            lines.append("Size ปรับตาม quintile (Q1 1.5× · Q5 0.5×)")
        msg = "\n".join(lines)
    else:
        msg = f"{header}\n\nไม่มีสัญญาณ BUY(dip) วันนี้"

    # Prefer the stateful managed watchlist (positions.json); fall back to the legacy
    # validated-candidates block only when no positions were passed.
    section = format_positions_section(holding, sell_today, t1_today,
                                       capital_info=capital_info)
    if not section:
        section = _format_validated_section(validated or [])
    if section:
        msg += "\n\n" + section
    return msg


_SIG_ABBR = {"dip": "dip", "breakout": "brk", "reclaim": "rcl", "golden": "gld"}


def _abbr_trigger(signals):
    """Compact trigger label (drops the broad 'trend' status)."""
    trig = [_SIG_ABBR[s] for s in signals if s in _SIG_ABBR]
    return "+".join(trig) or "trend"


def format_bull_message(shortlist, total, trend_count, tally, scan_date=""):
    """LINE text for the bullish scan: a Q1-leader-with-trigger shortlist + a signal legend +
    an AUTO analysis derived from the data (tight/low-risk vs extended vs overbought).
    shortlist: list of {ticker, signals, close, distPct, rsi, adx, buy?, stop?, t1?, size?}.
    total: universe size. trend_count: names in uptrend. tally: {signal: count}."""
    header = "SET Bull Scan"
    if scan_date:
        header += f" ({scan_date})"
    lines = [header, ""]
    breadth = f"ตลาด: {trend_count}/{total} ขาขึ้น"
    if total and trend_count >= 0.4 * total:
        breadth += " (บูลกว้าง)"
    lines.append(breadth)
    trg = "  ".join(f"{_SIG_ABBR[s]} {tally[s]}" for s in _SIG_ABBR if tally.get(s))
    if trg:
        lines.append("trigger: " + trg)

    if not shortlist:
        lines.append("\nวันนี้ไม่มี Q1 leader ที่มี trigger เข้าใหม่")
        return "\n".join(lines)

    lines.append(f"\n★ Q1 leader + trigger ({len(shortlist)}):")
    w = max([len(h["ticker"].replace(".BK", "")) for h in shortlist] + [6])
    hdr = f"{'Ticker':<{w}}  {'sig':<7}  {'Buy':>7}  {'Stop':>7}  {'T1':>7}  {'Size':>7}"
    lines += [hdr, "-" * len(hdr)]
    for h in shortlist:
        name = h["ticker"].replace(".BK", "")
        ext = "*" if h.get("distPct", 0) > 10 else ""       # extended >10% above EMA -> chase risk
        sz = h.get("size")
        sz_s = f"{sz:>7,d}" if isinstance(sz, (int, float)) and sz == sz else f"{'-':>7}"
        lines.append(f"{name:<{w}}  {_abbr_trigger(h['signals']):<7}  "
                     f"{_fmt_num(h.get('buy', h.get('close')), 7)}  {_fmt_num(h.get('stop'), 7)}  "
                     f"{_fmt_num(h.get('t1'), 7)}  {sz_s}{ext}")

    lines.append("\nBuy=ราคา limit วันถัดไป (ที่ราคานี้หรือดีกว่า) · dip=ย่อชน EMA เด้ง · "
                 "brk=นิวไฮ20วัน · rcl=กลับเหนือ EMA20")

    def nm(h):
        return h["ticker"].replace(".BK", "")
    low = [nm(h) for h in shortlist if h["distPct"] < 5 and h["adx"] >= 25]
    ext = [nm(h) + "*" for h in shortlist if h["distPct"] > 10]
    ob = [nm(h) for h in shortlist if h["rsi"] >= 78]
    notes = []
    if low:
        notes.append(f"เข้าง่าย/เสี่ยงต่ำ (ชิด EMA+ADXแข็ง): {', '.join(low)}")
    if ext:
        notes.append(f"ระวังยืด >10% (รอย่อ/ลดไซซ์): {', '.join(ext)}")
    if ob:
        notes.append(f"overbought RSI≥78: {', '.join(ob)}")
    if notes:
        lines.append("\nวิเคราะห์:\n- " + "\n- ".join(notes))
    lines.append("\n★=Q1 leader  *=ยืด >10% เหนือ EMA")
    return "\n".join(lines)
