#!/usr/bin/env python3
"""
trade_dashboard.py — local web dashboard for logging actual trade executions.

Start:  ~/.venvs/trading-dr/bin/python trade_dashboard.py
Open:   http://localhost:8060

Serves a single-page dashboard with:
  A. Plan Signals — latest dip/bull scan results + "enter trade" buttons
  B. Open Positions — actual open trades + "close trade" buttons
  C. Unplanned Trade — form for trades not from a system signal
  D. Plan vs Actual — closed trade comparison
  E. Quarterly Review — system metrics vs actual metrics side by side
"""
import csv
import glob
import json
import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import trade_log as tl

PORT = 8060


# ---------------------------------------------------------------- helpers

def _latest_csv(pattern):
    files = sorted(glob.glob(os.path.join(HERE, pattern)), reverse=True)
    return files[0] if files else None


def _read_csv(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _json_response(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    return json.loads(handler.rfile.read(length))


def _html_response(handler, html):
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


# ---------------------------------------------------------------- API

def api_get_trades(handler, params):
    data = tl.load()
    status = params.get("status", [None])[0]
    quarter = params.get("quarter", [None])[0]
    trades = data["trades"]
    if status:
        trades = [t for t in trades if t["status"] == status]
    if quarter:
        trades = [t for t in trades if t.get("quarter") == quarter]
    for t in trades:
        pl = tl.trade_pl(t)
        if pl:
            t["_pl"] = pl
        pva = tl.plan_vs_actual(t)
        if pva:
            t["_pva"] = pva
    _json_response(handler, trades)


def api_post_trade(handler):
    fields = _read_body(handler)
    data = tl.load()
    try:
        tid = tl.add_trade(data, fields)
        tl.save(data)
        _json_response(handler, {"id": tid}, 201)
    except ValueError as e:
        _json_response(handler, {"error": str(e)}, 400)


def api_put_trade(handler, trade_id):
    updates = _read_body(handler)
    data = tl.load()
    try:
        trade = tl.update_trade(data, trade_id, updates)
        tl.save(data)
        _json_response(handler, trade)
    except KeyError as e:
        _json_response(handler, {"error": str(e)}, 404)


def api_close_trade(handler, trade_id):
    fields = _read_body(handler)
    data = tl.load()
    try:
        trade = tl.close_trade(
            data, trade_id,
            fields["exit_date"], fields["exit_price"],
            fields["exit_reason"], fields.get("notes"),
        )
        tl.save(data)
        _json_response(handler, trade)
    except KeyError as e:
        _json_response(handler, {"error": str(e)}, 404)
    except ValueError as e:
        _json_response(handler, {"error": str(e)}, 400)


def api_delete_trade(handler, trade_id):
    data = tl.load()
    try:
        tl.cancel_trade(data, trade_id)
        tl.save(data)
        _json_response(handler, {"status": "cancelled"})
    except KeyError as e:
        _json_response(handler, {"error": str(e)}, 404)


def api_get_plan(handler):
    dip = _read_csv(_latest_csv("dip_scan_*.csv"))
    bull = _read_csv(_latest_csv("bull_scan_*.csv"))
    _json_response(handler, {"dip": dip, "bull": bull})


def api_get_quarter(handler):
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(HERE, "quarterly_review.py"), "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            _json_response(handler, json.loads(result.stdout))
        else:
            _json_response(handler, {"error": result.stderr or "no output"}, 500)
    except Exception as e:
        _json_response(handler, {"error": str(e)}, 500)


def api_get_positions(handler):
    path = os.path.join(HERE, "positions.json")
    try:
        with open(path) as f:
            _json_response(handler, json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        _json_response(handler, {})


def api_get_comparison(handler, params):
    quarter = params.get("quarter", [None])[0]
    data = tl.load()
    summary = tl.comparison_summary(data, quarter)
    closed = tl.closed_trades(data, quarter)
    trades_with_pva = []
    for t in closed:
        pl = tl.trade_pl(t)
        pva = tl.plan_vs_actual(t)
        trades_with_pva.append({**t, "_pl": pl, "_pva": pva})
    actual_m = None
    if closed:
        try:
            actual_m = tl.actual_metrics(closed)
        except Exception:
            pass
    _json_response(handler, {
        "summary": summary,
        "trades": trades_with_pva,
        "actual_metrics": actual_m,
    })


# ---------------------------------------------------------------- routing

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default logging

    def _route(self, method):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        if method == "GET" and path == "":
            return _html_response(self, DASHBOARD_HTML)
        if method == "GET" and path == "/api/trades":
            return api_get_trades(self, params)
        if method == "POST" and path == "/api/trades":
            return api_post_trade(self)
        if method == "GET" and path == "/api/plan":
            return api_get_plan(self)
        if method == "GET" and path == "/api/quarter":
            return api_get_quarter(self)
        if method == "GET" and path == "/api/positions":
            return api_get_positions(self)
        if method == "GET" and path == "/api/comparison":
            return api_get_comparison(self, params)

        # /api/trades/<id>/close or /api/trades/<id>
        parts = path.split("/")
        if len(parts) >= 4 and parts[1] == "api" and parts[2] == "trades":
            trade_id = parts[3]
            if len(parts) == 5 and parts[4] == "close" and method == "POST":
                return api_close_trade(self, trade_id)
            if method == "PUT":
                return api_put_trade(self, trade_id)
            if method == "DELETE":
                return api_delete_trade(self, trade_id)

        self.send_error(404)

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PUT(self):
        self._route("PUT")

    def do_DELETE(self):
        self._route("DELETE")


# ---------------------------------------------------------------- HTML

DASHBOARD_HTML = r"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trade Dashboard — DW Swing</title>
<style>
:root {
  --bg: #FAFAF8; --bg2: #FFF; --bg3: #F5F5F3; --bg4: #EBEBEA;
  --fg: #1E1E1F; --fg2: #5C5C5E; --fg3: #8A8A8C;
  --border: #D8D8D6;
  --gold: #A67C00; --gold-bg: #FFF8E1; --gold-bd: #E8D48B;
  --green: #16803C; --green-bg: #ECFDF5;
  --red: #C53030; --red-bg: #FFF5F5;
  --blue: #2563EB; --blue-bg: #EFF6FF;
  --teal: #0D7377; --teal-bg: #F0FDFA;
  --ribbon: #1C1F26; --ribbon-fg: #E5E5E3; --ribbon-m: #9CA3AF;
  --accent: #B8860B;
}
@media(prefers-color-scheme:dark){:root{
  --bg:#111318;--bg2:#1A1D24;--bg3:#1E2128;--bg4:#252830;
  --fg:#E5E5E3;--fg2:#9CA3AF;--fg3:#6B7280;
  --border:#2E3138;
  --gold:#D4A853;--gold-bg:#2A2415;--gold-bd:#554A2A;
  --green:#34D399;--green-bg:#0D2818;
  --red:#F87171;--red-bg:#2D1515;
  --blue:#60A5FA;--blue-bg:#172038;
  --teal:#2DD4BF;--teal-bg:#0D2D2D;
  --ribbon:#0D0F13;--ribbon-fg:#E5E5E3;--ribbon-m:#6B7280;
  --accent:#D4A853;
}}
:root[data-theme="dark"]{
  --bg:#111318;--bg2:#1A1D24;--bg3:#1E2128;--bg4:#252830;
  --fg:#E5E5E3;--fg2:#9CA3AF;--fg3:#6B7280;
  --border:#2E3138;
  --gold:#D4A853;--gold-bg:#2A2415;--gold-bd:#554A2A;
  --green:#34D399;--green-bg:#0D2818;
  --red:#F87171;--red-bg:#2D1515;
  --blue:#60A5FA;--blue-bg:#172038;
  --teal:#2DD4BF;--teal-bg:#0D2D2D;
  --ribbon:#0D0F13;--ribbon-fg:#E5E5E3;--ribbon-m:#6B7280;
  --accent:#D4A853;
}
:root[data-theme="light"]{
  --bg:#FAFAF8;--bg2:#FFF;--bg3:#F5F5F3;--bg4:#EBEBEA;
  --fg:#1E1E1F;--fg2:#5C5C5E;--fg3:#8A8A8C;
  --border:#D8D8D6;
  --gold:#A67C00;--gold-bg:#FFF8E1;--gold-bd:#E8D48B;
  --green:#16803C;--green-bg:#ECFDF5;
  --red:#C53030;--red-bg:#FFF5F5;
  --blue:#2563EB;--blue-bg:#EFF6FF;
  --teal:#0D7377;--teal-bg:#F0FDFA;
  --ribbon:#1C1F26;--ribbon-fg:#E5E5E3;--ribbon-m:#9CA3AF;
  --accent:#B8860B;
}

*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;font-variant-numeric:tabular-nums;line-height:1.5}

.ribbon{background:var(--ribbon);color:var(--ribbon-fg);padding:12px 24px;display:flex;flex-wrap:wrap;gap:16px;align-items:center;border-bottom:2px solid var(--accent)}
.ribbon-title{font-size:15px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--accent);margin-right:auto}
.ribbon-stat{font-family:'SF Mono',Menlo,Consolas,monospace;font-size:12px;color:var(--ribbon-m)}
.ribbon-stat b{color:var(--ribbon-fg);font-weight:600}

.tabs{display:flex;gap:0;border-bottom:1px solid var(--border);background:var(--bg2);overflow-x:auto}
.tab{padding:10px 20px;font-size:13px;font-weight:600;color:var(--fg3);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap;transition:all .15s}
.tab:hover{color:var(--fg)}
.tab.active{color:var(--accent);border-bottom-color:var(--accent)}

.container{max-width:960px;margin:0 auto;padding:20px}
.panel{display:none}
.panel.active{display:block}

.card{background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:16px;margin-bottom:12px}
.card h3{font-size:14px;font-weight:700;margin-bottom:10px}

.tw{overflow-x:auto;border:1px solid var(--border);border-radius:6px}
table{width:100%;border-collapse:collapse;font-size:12px;min-width:600px}
thead th{background:var(--bg3);font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--fg3);padding:7px 8px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap}
thead th:first-child{text-align:left}
tbody tr{border-bottom:1px solid var(--border)}
tbody tr:nth-child(even){background:var(--bg3)}
td{padding:7px 8px;text-align:right;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:11px;white-space:nowrap}
td:first-child{text-align:left;font-family:inherit;font-weight:600;font-size:12px}

.q{display:inline-block;font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px;letter-spacing:.04em}
.q1{background:var(--gold-bg);color:var(--gold);border:1px solid var(--gold-bd)}
.q2{background:var(--blue-bg);color:var(--blue)}

.sig{display:inline-block;font-size:9px;font-weight:600;padding:1px 4px;border-radius:3px;text-transform:uppercase}
.sig-dip{background:var(--teal-bg);color:var(--teal)}
.sig-brk{background:var(--blue-bg);color:var(--blue)}
.sig-trend{background:var(--bg3);color:var(--fg3)}

.stop{color:var(--red)} .t1{color:var(--green)} .pos{color:var(--green)} .neg{color:var(--red)}

.btn{padding:5px 12px;font-size:11px;font-weight:600;border:1px solid var(--border);border-radius:4px;background:var(--bg2);color:var(--fg);cursor:pointer;transition:all .1s}
.btn:hover{background:var(--bg3)}
.btn-primary{background:var(--accent);color:#fff;border-color:var(--accent)}
.btn-primary:hover{opacity:.9}
.btn-sm{padding:3px 8px;font-size:10px}

.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:100;justify-content:center;align-items:center}
.modal-bg.show{display:flex}
.modal{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:24px;width:90%;max-width:500px;max-height:90vh;overflow-y:auto}
.modal h3{font-size:15px;font-weight:700;margin-bottom:16px}
.field{margin-bottom:12px}
.field label{display:block;font-size:11px;font-weight:600;color:var(--fg3);text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px}
.field input,.field select{width:100%;padding:7px 10px;font-size:13px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--fg);font-family:inherit}
.field input:focus,.field select:focus{outline:none;border-color:var(--accent)}
.field-row{display:flex;gap:10px}
.field-row .field{flex:1}
.field .hint{font-size:10px;color:var(--fg3);margin-top:2px}
.modal-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:16px}

.toast{position:fixed;bottom:20px;right:20px;padding:10px 16px;border-radius:6px;font-size:13px;font-weight:600;z-index:200;opacity:0;transition:opacity .3s}
.toast.show{opacity:1}
.toast-ok{background:var(--green-bg);color:var(--green);border:1px solid var(--green)}
.toast-err{background:var(--red-bg);color:var(--red);border:1px solid var(--red)}

.empty{text-align:center;padding:40px;color:var(--fg3);font-size:13px}

.stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:16px}
.stat-card{background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:12px}
.stat-label{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:var(--fg3)}
.stat-val{font-family:'SF Mono',Menlo,Consolas,monospace;font-size:18px;font-weight:700;margin-top:2px}
.stat-sub{font-size:11px;color:var(--fg2);margin-top:2px}
</style>
</head>
<body>

<div class="ribbon">
  <span class="ribbon-title">Trade Dashboard</span>
  <span class="ribbon-stat">Port <b>8060</b></span>
  <span class="ribbon-stat" id="r-equity"></span>
  <span class="ribbon-stat" id="r-trades"></span>
</div>

<div class="tabs" id="tabs">
  <div class="tab active" data-tab="plan">Plan Signals</div>
  <div class="tab" data-tab="open">Open Trades</div>
  <div class="tab" data-tab="unplanned">+Unplanned</div>
  <div class="tab" data-tab="compare">Plan vs Actual</div>
  <div class="tab" data-tab="quarter">Quarter Review</div>
</div>

<div class="container">
  <!-- A: Plan Signals -->
  <div class="panel active" id="p-plan">
    <div id="plan-content"><div class="empty">Loading...</div></div>
  </div>

  <!-- B: Open Trades -->
  <div class="panel" id="p-open">
    <div id="open-content"><div class="empty">Loading...</div></div>
  </div>

  <!-- C: Unplanned Trade -->
  <div class="panel" id="p-unplanned">
    <div class="card">
      <h3>Log Unplanned Trade</h3>
      <form id="unplanned-form">
        <div class="field-row">
          <div class="field"><label>Ticker</label><input name="ticker" placeholder="e.g. STECON" required></div>
          <div class="field"><label>Entry Date</label><input name="entry_date" type="date" required></div>
        </div>
        <div class="field-row">
          <div class="field"><label>Entry Price</label><input name="entry_price" type="number" step="0.01" required></div>
          <div class="field"><label>Entry Size</label><input name="entry_size" type="number" required><div class="hint" id="lot-hint-u"></div></div>
        </div>
        <div class="field"><label>Notes</label><input name="notes" placeholder="optional"></div>
        <div class="modal-actions"><button type="submit" class="btn btn-primary">Save Trade</button></div>
      </form>
    </div>
  </div>

  <!-- D: Plan vs Actual -->
  <div class="panel" id="p-compare">
    <div id="compare-content"><div class="empty">Loading...</div></div>
  </div>

  <!-- E: Quarter Review -->
  <div class="panel" id="p-quarter">
    <div id="quarter-content"><div class="empty">Loading...</div></div>
  </div>
</div>

<!-- Modal: Enter Trade -->
<div class="modal-bg" id="modal-enter">
  <div class="modal">
    <h3 id="modal-enter-title">Enter Trade</h3>
    <form id="enter-form">
      <input type="hidden" name="plan_date">
      <input type="hidden" name="plan_signal">
      <input type="hidden" name="plan_buy">
      <input type="hidden" name="plan_stop">
      <input type="hidden" name="plan_t1">
      <input type="hidden" name="plan_size">
      <input type="hidden" name="plan_quintile">
      <input type="hidden" name="ticker">
      <div class="field-row">
        <div class="field"><label>Ticker</label><input name="_ticker_display" disabled></div>
        <div class="field"><label>Plan Signal</label><input name="_signal_display" disabled></div>
      </div>
      <div class="field-row">
        <div class="field"><label>Plan Buy</label><input name="_plan_buy_display" disabled></div>
        <div class="field"><label>Plan Size</label><input name="_plan_size_display" disabled></div>
      </div>
      <hr style="border:none;border-top:1px solid var(--border);margin:12px 0">
      <div class="field-row">
        <div class="field"><label>Actual Entry Date</label><input name="entry_date" type="date" required></div>
        <div class="field"><label>Actual Entry Price</label><input name="entry_price" type="number" step="0.01" required></div>
      </div>
      <div class="field-row">
        <div class="field"><label>Actual Size</label><input name="entry_size" type="number" required><div class="hint" id="lot-hint-e"></div></div>
        <div class="field"><label>DW?</label><select name="is_dw"><option value="">No</option><option value="1">Yes</option></select></div>
      </div>
      <div class="field" id="dw-field" style="display:none"><label>DW Series</label><input name="dw_series" placeholder="e.g. STECON01C2609A"></div>
      <div class="field"><label>Notes</label><input name="notes" placeholder="optional"></div>
      <div class="modal-actions">
        <button type="button" class="btn" onclick="closeModal('modal-enter')">Cancel</button>
        <button type="submit" class="btn btn-primary">Save</button>
      </div>
    </form>
  </div>
</div>

<!-- Modal: Close Trade -->
<div class="modal-bg" id="modal-close">
  <div class="modal">
    <h3 id="modal-close-title">Close Trade</h3>
    <form id="close-form">
      <input type="hidden" name="trade_id">
      <div class="field-row">
        <div class="field"><label>Exit Date</label><input name="exit_date" type="date" required></div>
        <div class="field"><label>Exit Price</label><input name="exit_price" type="number" step="0.01" required></div>
      </div>
      <div class="field"><label>Exit Reason</label>
        <select name="exit_reason" required>
          <option value="">-- select --</option>
          <option value="STOP">STOP</option>
          <option value="TRAIL">TRAIL (EMA20)</option>
          <option value="BE">BE (Breakeven)</option>
          <option value="T1">T1 (+1R)</option>
          <option value="MANUAL">MANUAL</option>
        </select>
      </div>
      <div class="field"><label>Notes</label><input name="notes" placeholder="optional"></div>
      <div class="modal-actions">
        <button type="button" class="btn" onclick="closeModal('modal-close')">Cancel</button>
        <button type="submit" class="btn btn-primary">Close Trade</button>
      </div>
    </form>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const today = () => new Date().toISOString().slice(0,10);

// ---- tabs ----
$$('.tab').forEach(t => t.addEventListener('click', () => {
  $$('.tab').forEach(x => x.classList.remove('active'));
  $$('.panel').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  $(`#p-${t.dataset.tab}`).classList.add('active');
  loadTab(t.dataset.tab);
}));

function loadTab(tab) {
  if (tab === 'plan') loadPlan();
  if (tab === 'open') loadOpen();
  if (tab === 'compare') loadCompare();
  if (tab === 'quarter') loadQuarter();
}

// ---- toast ----
function toast(msg, ok=true) {
  const el = $('#toast');
  el.textContent = msg;
  el.className = 'toast show ' + (ok ? 'toast-ok' : 'toast-err');
  setTimeout(() => el.classList.remove('show'), 2500);
}

// ---- modal ----
function openModal(id) { $(`#${id}`).classList.add('show'); }
function closeModal(id) { $(`#${id}`).classList.remove('show'); }

// ---- helpers ----
function qBadge(q) {
  if (!q) return '';
  q = parseInt(q);
  const cls = q <= 1 ? 'q1' : q <= 2 ? 'q2' : '';
  return `<span class="q ${cls}">Q${q}</span>`;
}
function sigBadge(s) {
  if (!s) return '';
  const signals = s.split('|');
  return signals.map(x => {
    const cls = x === 'dip' ? 'sig-dip' : x === 'breakout' ? 'sig-brk' : 'sig-trend';
    return `<span class="sig ${cls}">${x}</span>`;
  }).join(' ');
}
function fmt(n, d=2) { return n != null ? parseFloat(n).toFixed(d) : '-'; }
function fmtK(n) { return n != null ? parseFloat(n).toLocaleString('en',{maximumFractionDigits:0}) : '-'; }
function plClass(n) { return parseFloat(n) >= 0 ? 'pos' : 'neg'; }
function lotHint(input, hintId) {
  const el = $(`#${hintId}`);
  if (!el) return;
  input.addEventListener('input', () => {
    const v = parseInt(input.value);
    if (v > 0) el.textContent = `Board lot: ${Math.floor(v/100)*100}`;
    else el.textContent = '';
  });
}

// ---- A: Plan Signals ----
async function loadPlan() {
  try {
    const res = await fetch('/api/plan');
    const data = await res.json();
    const dip = data.dip || [];
    const bull = data.bull || [];

    let html = '';
    if (dip.length) {
      html += '<div class="card"><h3>Validated Dip Signals</h3><div class="tw"><table>';
      html += '<thead><tr><th>Ticker</th><th>Q</th><th>Signal</th><th>Buy</th><th>Stop</th><th>T1</th><th>Size</th><th>RSI</th><th>ADX</th><th></th></tr></thead><tbody>';
      for (const r of dip) {
        if (r.validated !== 'True') continue;
        const tk = (r.ticker||'').replace('.BK','');
        html += `<tr>
          <td>${tk}</td>
          <td>${qBadge(r.quintile)}</td>
          <td><span class="sig sig-dip">DIP</span></td>
          <td>${fmt(r.buy||r.close)}</td>
          <td class="stop">${fmt(r.stop)}</td>
          <td class="t1">${fmt(r.t1)}</td>
          <td>${fmtK(r.size)}</td>
          <td>${fmt(r.rsi,0)}</td>
          <td>${fmt(r.adx,0)}</td>
          <td><button class="btn btn-sm" onclick='enterFromPlan(${JSON.stringify(r)}, "dip")'>Enter</button></td>
        </tr>`;
      }
      html += '</tbody></table></div></div>';
    }

    // breakout signals from bull scan
    const brk = bull.filter(r => (r.signals||'').includes('breakout'));
    if (brk.length) {
      html += '<div class="card"><h3>Breakout Signals</h3><div class="tw"><table>';
      html += '<thead><tr><th>Ticker</th><th>Q</th><th>Signals</th><th>Close</th><th>Stop</th><th>T1</th><th>Size</th><th>RSI</th><th></th></tr></thead><tbody>';
      for (const r of brk) {
        const tk = (r.ticker||'').replace('.BK','');
        html += `<tr>
          <td>${tk}</td>
          <td>${qBadge(r.quintile)}</td>
          <td>${sigBadge(r.signals)}</td>
          <td>${fmt(r.close)}</td>
          <td class="stop">${fmt(r.stop)}</td>
          <td class="t1">${fmt(r.t1)}</td>
          <td>${fmtK(r.size)}</td>
          <td>${fmt(r.rsi,0)}</td>
          <td><button class="btn btn-sm" onclick='enterFromPlan(${JSON.stringify(r)}, "breakout")'>Enter</button></td>
        </tr>`;
      }
      html += '</tbody></table></div></div>';
    }

    if (!html) html = '<div class="empty">No validated signals found</div>';
    $('#plan-content').innerHTML = html;
  } catch(e) {
    $('#plan-content').innerHTML = `<div class="empty">Error: ${e.message}</div>`;
  }
}

function enterFromPlan(row, signal) {
  const f = $('#enter-form');
  const tk = (row.ticker||'').replace('.BK','');
  f.ticker.value = row.ticker || '';
  f._ticker_display.value = tk;
  f._signal_display.value = signal;
  f.plan_signal.value = signal;
  f.plan_date.value = row.asof || today();
  f.plan_buy.value = row.buy || row.close || '';
  f._plan_buy_display.value = fmt(row.buy || row.close);
  f.plan_stop.value = row.stop || '';
  f.plan_t1.value = row.t1 || '';
  f.plan_size.value = row.size || '';
  f._plan_size_display.value = fmtK(row.size);
  f.plan_quintile.value = row.quintile || '';
  f.entry_date.value = today();
  f.entry_price.value = row.buy || row.close || '';
  f.entry_size.value = row.size ? Math.floor(parseInt(row.size)/100)*100 : '';
  f.is_dw.value = '';
  f.dw_series.value = '';
  f.notes.value = '';
  $('#dw-field').style.display = 'none';
  $('#modal-enter-title').textContent = `Enter Trade: ${tk}`;
  openModal('modal-enter');
}

// ---- B: Open Trades ----
async function loadOpen() {
  try {
    const res = await fetch('/api/trades?status=open');
    const trades = await res.json();
    if (!trades.length) {
      $('#open-content').innerHTML = '<div class="empty">No open trades</div>';
      return;
    }
    let html = '<div class="tw"><table>';
    html += '<thead><tr><th>Ticker</th><th>Q</th><th>Signal</th><th>Entry Date</th><th>Entry Price</th><th>Size</th><th>Plan Stop</th><th>Plan T1</th><th>Notes</th><th></th></tr></thead><tbody>';
    for (const t of trades) {
      const tk = (t.ticker||'').replace('.BK','');
      html += `<tr>
        <td>${tk}</td>
        <td>${qBadge(t.plan_quintile)}</td>
        <td>${sigBadge(t.plan_signal||'')}</td>
        <td>${t.entry_date}</td>
        <td>${fmt(t.entry_price)}</td>
        <td>${fmtK(t.entry_size)}</td>
        <td class="stop">${fmt(t.plan_stop)}</td>
        <td class="t1">${fmt(t.plan_t1)}</td>
        <td style="font-family:inherit;font-size:11px">${t.notes||''}</td>
        <td><button class="btn btn-sm" onclick='closeTrade("${t.id}","${tk}")'>Close</button></td>
      </tr>`;
    }
    html += '</tbody></table></div>';
    $('#open-content').innerHTML = html;
    $('#r-trades').innerHTML = `Open <b>${trades.length}</b>`;
  } catch(e) {
    $('#open-content').innerHTML = `<div class="empty">Error: ${e.message}</div>`;
  }
}

function closeTrade(id, ticker) {
  const f = $('#close-form');
  f.trade_id.value = id;
  f.exit_date.value = today();
  f.exit_price.value = '';
  f.exit_reason.value = '';
  f.notes.value = '';
  $('#modal-close-title').textContent = `Close: ${ticker}`;
  openModal('modal-close');
}

// ---- D: Plan vs Actual ----
async function loadCompare() {
  try {
    const res = await fetch('/api/comparison');
    const data = await res.json();
    const {summary, trades} = data;

    let html = '';
    if (summary) {
      html += '<div class="stat-grid">';
      html += `<div class="stat-card"><div class="stat-label">Total Trades</div><div class="stat-val">${summary.total_trades}</div><div class="stat-sub">${summary.planned_trades} planned, ${summary.unplanned_trades} unplanned</div></div>`;
      html += `<div class="stat-card"><div class="stat-label">Avg Slippage</div><div class="stat-val ${plClass(-(summary.avg_slippage_pct||0))}">${summary.avg_slippage_pct != null ? fmt(summary.avg_slippage_pct)+'%' : '-'}</div><div class="stat-sub">negative = better than plan</div></div>`;
      html += `<div class="stat-card"><div class="stat-label">Avg R-Multiple</div><div class="stat-val">${summary.avg_actual_rr != null ? fmt(summary.avg_actual_rr) : '-'}</div><div class="stat-sub">T1 = +1R</div></div>`;
      html += `<div class="stat-card"><div class="stat-label">T1 Hit Rate</div><div class="stat-val">${summary.t1_hit_rate != null ? fmt(summary.t1_hit_rate,1)+'%' : '-'}</div></div>`;
      html += '</div>';
    }

    if (trades && trades.length) {
      html += '<div class="tw"><table>';
      html += '<thead><tr><th>Ticker</th><th>Signal</th><th>Plan Buy</th><th>Actual Entry</th><th>Slip%</th><th>Plan Size</th><th>Actual Size</th><th>Exit</th><th>Reason</th><th>R-mult</th><th>P/L%</th><th>P/L ฿</th></tr></thead><tbody>';
      for (const t of trades) {
        const tk = (t.ticker||'').replace('.BK','');
        const pva = t._pva || {};
        const pl = t._pl || {};
        html += `<tr>
          <td>${tk}</td>
          <td>${sigBadge(t.plan_signal||'manual')}</td>
          <td>${fmt(t.plan_buy)}</td>
          <td>${fmt(t.entry_price)}</td>
          <td class="${plClass(-(pva.entry_slippage_pct||0))}">${pva.entry_slippage_pct != null ? fmt(pva.entry_slippage_pct)+'%' : '-'}</td>
          <td>${fmtK(t.plan_size)}</td>
          <td>${fmtK(t.entry_size)}</td>
          <td>${fmt(t.exit_price)}</td>
          <td>${t.exit_reason||'-'}</td>
          <td>${pva.actual_rr != null ? fmt(pva.actual_rr) : '-'}</td>
          <td class="${plClass(pl.pl_pct||0)}">${pl.pl_pct != null ? fmt(pl.pl_pct)+'%' : '-'}</td>
          <td class="${plClass(pl.pl_baht||0)}">${pl.pl_baht != null ? fmtK(pl.pl_baht) : '-'}</td>
        </tr>`;
      }
      html += '</tbody></table></div>';
    } else {
      html += '<div class="empty">No closed trades yet</div>';
    }
    $('#compare-content').innerHTML = html;
  } catch(e) {
    $('#compare-content').innerHTML = `<div class="empty">Error: ${e.message}</div>`;
  }
}

// ---- E: Quarter Review ----
async function loadQuarter() {
  try {
    const [qRes, cRes] = await Promise.all([
      fetch('/api/quarter'),
      fetch('/api/comparison')
    ]);
    const qData = await qRes.json();
    const cData = await cRes.json();

    let html = '';

    // system metrics
    const sm = qData.metrics || {};
    const bs = qData.budget_status || {};
    html += '<div class="card"><h3>System Metrics (from git history)</h3>';
    if (sm.n === 0) {
      html += '<div class="empty">No closed trades in system yet</div>';
    } else {
      html += '<div class="stat-grid">';
      html += `<div class="stat-card"><div class="stat-label">Expectancy</div><div class="stat-val">${fmt(sm.expectancy_pct)}%</div><div class="stat-sub">${fmtK(sm.expectancy_baht)} ฿/trade</div></div>`;
      html += `<div class="stat-card"><div class="stat-label">Profit Factor</div><div class="stat-val">${sm.profit_factor != null ? fmt(sm.profit_factor) : '-'}</div><div class="stat-sub">target >= 1.9</div></div>`;
      html += `<div class="stat-card"><div class="stat-label">Win Rate</div><div class="stat-val">${fmt((sm.winrate||0)*100,0)}%</div><div class="stat-sub">${sm.wins||0}W / ${sm.losses||0}L</div></div>`;
      html += `<div class="stat-card"><div class="stat-label">Max DD</div><div class="stat-val neg">${fmtK(sm.max_dd_baht)} ฿</div></div>`;
      html += '</div>';
    }
    if (bs.total !== undefined) {
      const cls = bs.breached ? 'neg' : 'pos';
      html += `<div style="font-size:12px;color:var(--fg2);margin-top:8px">Risk Budget: <span class="${cls}">${fmt(bs.dd_pct)}%</span> / -${bs.limit}% limit (${bs.breached ? 'BREACH' : 'OK'})</div>`;
    }
    html += '</div>';

    // actual metrics
    const am = cData.actual_metrics;
    if (am && am.metrics && am.metrics.n > 0) {
      const m = am.metrics;
      html += '<div class="card"><h3>Actual Metrics (from trade log)</h3>';
      html += '<div class="stat-grid">';
      html += `<div class="stat-card"><div class="stat-label">Expectancy</div><div class="stat-val">${fmt(m.expectancy_pct)}%</div><div class="stat-sub">${fmtK(m.expectancy_baht)} ฿/trade</div></div>`;
      html += `<div class="stat-card"><div class="stat-label">Profit Factor</div><div class="stat-val">${m.profit_factor != null ? fmt(m.profit_factor) : '-'}</div></div>`;
      html += `<div class="stat-card"><div class="stat-label">Win Rate</div><div class="stat-val">${fmt((m.winrate||0)*100,0)}%</div><div class="stat-sub">${m.wins||0}W / ${m.losses||0}L</div></div>`;
      html += `<div class="stat-card"><div class="stat-label">Total P/L</div><div class="stat-val ${plClass(m.total_baht||0)}">${fmtK(m.total_baht)} ฿</div></div>`;
      html += '</div></div>';
    } else {
      html += '<div class="card"><h3>Actual Metrics</h3><div class="empty">No closed trades in trade log yet</div></div>';
    }

    $('#quarter-content').innerHTML = html;
    if (bs.total !== undefined) {
      const eq = qData.budget ? qData.budget.start_equity : 100000;
      $('#r-equity').innerHTML = `Equity <b>${fmtK(eq)}</b>`;
    }
  } catch(e) {
    $('#quarter-content').innerHTML = `<div class="empty">Error: ${e.message}</div>`;
  }
}

// ---- form handlers ----
$('#enter-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.target;
  const body = {
    ticker: f.ticker.value,
    entry_date: f.entry_date.value,
    entry_price: parseFloat(f.entry_price.value),
    entry_size: parseInt(f.entry_size.value),
    plan_date: f.plan_date.value || null,
    plan_signal: f.plan_signal.value || null,
    plan_buy: parseFloat(f.plan_buy.value) || null,
    plan_stop: parseFloat(f.plan_stop.value) || null,
    plan_t1: parseFloat(f.plan_t1.value) || null,
    plan_size: parseInt(f.plan_size.value) || null,
    plan_quintile: parseInt(f.plan_quintile.value) || null,
    is_dw: f.is_dw.value === '1',
    dw_series: f.dw_series.value || null,
    notes: f.notes.value || '',
  };
  try {
    const res = await fetch('/api/trades', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
    const data = await res.json();
    if (res.ok) {
      toast(`Trade ${data.id} saved`);
      closeModal('modal-enter');
      loadOpen();
    } else {
      toast(data.error || 'Error', false);
    }
  } catch(err) { toast(err.message, false); }
});

$('#close-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.target;
  const id = f.trade_id.value;
  const body = {
    exit_date: f.exit_date.value,
    exit_price: parseFloat(f.exit_price.value),
    exit_reason: f.exit_reason.value,
    notes: f.notes.value || null,
  };
  try {
    const res = await fetch(`/api/trades/${id}/close`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
    const data = await res.json();
    if (res.ok) {
      toast(`Trade ${id} closed`);
      closeModal('modal-close');
      loadOpen();
    } else {
      toast(data.error || 'Error', false);
    }
  } catch(err) { toast(err.message, false); }
});

$('#unplanned-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.target;
  const body = {
    ticker: f.ticker.value,
    entry_date: f.entry_date.value,
    entry_price: parseFloat(f.entry_price.value),
    entry_size: parseInt(f.entry_size.value),
    notes: f.notes.value || '',
  };
  try {
    const res = await fetch('/api/trades', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
    const data = await res.json();
    if (res.ok) {
      toast(`Trade ${data.id} saved`);
      f.reset();
      loadOpen();
    } else {
      toast(data.error || 'Error', false);
    }
  } catch(err) { toast(err.message, false); }
});

// DW toggle
$('[name="is_dw"]').addEventListener('change', (e) => {
  $('#dw-field').style.display = e.target.value === '1' ? 'block' : 'none';
});

// board-lot hints
lotHint($('#enter-form [name="entry_size"]'), 'lot-hint-e');
lotHint($('#unplanned-form [name="entry_size"]'), 'lot-hint-u');

// ---- init ----
loadPlan();
loadOpen();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------- main

def main():
    print(f"Trade Dashboard at http://localhost:{PORT}")
    print("Press Ctrl+C to stop\n")
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
