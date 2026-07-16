#!/usr/bin/env python3
"""
viewer.py — live web viewer for dip_scan_*.csv results.

Start:  ~/.venvs/trading-dr/bin/python viewer.py
Open:   http://localhost:8050
"""
import asyncio
import glob
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

HERE = Path(__file__).resolve().parent
SCANS_DIR = HERE / "scans"          # dated dip_scan_*.csv outputs
PORT = 8050

app = FastAPI()

# --- SSE plumbing -----------------------------------------------------------

_clients: list[asyncio.Queue] = []


class _CsvHandler(FileSystemEventHandler):
    def on_created(self, event):
        self._notify(event.src_path)

    def on_modified(self, event):
        self._notify(event.src_path)

    @staticmethod
    def _notify(path):
        if "dip_scan_" in os.path.basename(path) and path.endswith(".csv"):
            for q in list(_clients):
                q.put_nowait("reload")


def _start_watcher():
    handler = _CsvHandler()
    observer = Observer()
    observer.schedule(handler, str(SCANS_DIR), recursive=False)
    observer.daemon = True
    observer.start()


# --- CSV parsing -------------------------------------------------------------

_TS_RE = re.compile(
    r"dip_scan_(\d{4}-\d{2}-\d{2})(?:_(\d{8}_\d{6}))?\.csv$"
)


def _parse_filename(name: str):
    m = _TS_RE.search(name)
    if not m:
        return None, None
    scan_date = m.group(1)
    if m.group(2):
        run_time = datetime.strptime(m.group(2), "%Y%m%d_%H%M%S").isoformat()
    else:
        ts = os.path.getmtime(os.path.join(SCANS_DIR, name))
        run_time = datetime.fromtimestamp(ts).isoformat()
    return scan_date, run_time


def _load_scans():
    files = sorted(glob.glob(str(SCANS_DIR / "dip_scan_*.csv")), reverse=True)
    scans = []
    for fpath in files:
        name = os.path.basename(fpath)
        scan_date, run_time = _parse_filename(name)
        if scan_date is None:
            continue
        try:
            df = pd.read_csv(fpath)
            rows = df.to_dict(orient="records") if len(df) > 0 else []
            hits = [
                {k: (None if isinstance(v, float) and pd.isna(v) else v)
                 for k, v in row.items()}
                for row in rows
            ]
        except Exception:
            hits = []
        scans.append({
            "filename": name,
            "scan_date": scan_date,
            "run_time": run_time,
            "hits": hits,
        })
    scans.sort(key=lambda s: (s["scan_date"], s["run_time"]), reverse=True)
    return scans


# --- Routes ------------------------------------------------------------------

@app.get("/api/scans")
def api_scans():
    return {"scans": _load_scans()}


@app.get("/api/events")
async def api_events(request: Request):
    q: asyncio.Queue = asyncio.Queue()
    _clients.append(q)

    async def stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"event: {msg}\ndata: {{}}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _clients.remove(q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE


# --- Embedded HTML -----------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SET DW Swing — Scan Results</title>
<style>
  :root {
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --red: #f85149; --yellow: #d29922;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text); padding: 24px; line-height: 1.5;
  }
  header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border);
  }
  header h1 { font-size: 20px; font-weight: 600; }
  .status {
    font-size: 12px; padding: 4px 10px; border-radius: 12px;
    background: var(--surface); border: 1px solid var(--border);
  }
  .status.live { border-color: var(--green); color: var(--green); }
  .scan-group {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; margin-bottom: 16px; overflow: hidden;
  }
  .scan-header {
    padding: 12px 16px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 12px;
  }
  .scan-header .date { font-weight: 600; font-size: 15px; }
  .scan-header .time { color: var(--muted); font-size: 13px; }
  .scan-header .count {
    margin-left: auto; font-size: 12px; padding: 2px 8px;
    border-radius: 10px; background: var(--accent); color: #fff; font-weight: 600;
  }
  .scan-header .count.zero { background: var(--border); color: var(--muted); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th {
    text-align: left; padding: 8px 12px; color: var(--muted);
    font-weight: 500; font-size: 11px; text-transform: uppercase;
    letter-spacing: 0.5px; border-bottom: 1px solid var(--border);
  }
  td { padding: 8px 12px; border-bottom: 1px solid var(--border); }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(88,166,255,0.04); }
  .ticker { font-weight: 600; color: var(--accent); }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  .pos { color: var(--green); }
  .neg { color: var(--red); }
  .empty {
    padding: 24px; text-align: center; color: var(--muted); font-size: 14px;
  }
  .no-data {
    text-align: center; padding: 60px 24px; color: var(--muted);
  }
  .no-data h2 { font-size: 18px; margin-bottom: 8px; color: var(--text); }
  .badge {
    font-size: 11px; padding: 2px 8px; border-radius: 10px;
    font-weight: 600; display: inline-block; white-space: nowrap;
  }
  .badge.ok { background: rgba(63,185,80,0.15); color: var(--green); }
  .badge.fail { background: rgba(248,81,73,0.15); color: var(--red); }
  .badge.unknown { background: rgba(139,148,158,0.15); color: var(--muted); }
  .val-reason { color: var(--muted); font-size: 11px; margin-left: 4px; }
  .val-date { color: var(--muted); font-size: 11px; }
</style>
</head>
<body>

<header>
  <h1>SET DW Swing &mdash; Scan Results</h1>
  <span class="status" id="status">connecting&hellip;</span>
</header>

<div id="content"><div class="no-data"><h2>Loading&hellip;</h2></div></div>

<script>
const $content = document.getElementById('content');
const $status  = document.getElementById('status');

function fmt(v, dec=2) {
  if (v == null || v === '') return '—';
  const n = Number(v);
  return isNaN(n) ? v : n.toLocaleString(undefined, {minimumFractionDigits: dec, maximumFractionDigits: dec});
}
function fmtInt(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString();
}
function distClass(v) {
  return v > 0 ? 'pos' : v < 0 ? 'neg' : '';
}

function render(scans) {
  if (!scans || scans.length === 0) {
    $content.innerHTML = '<div class="no-data"><h2>No scan results</h2><p>Run scan_dip.py to generate results.</p></div>';
    return;
  }
  let html = '';
  for (const s of scans) {
    const d = s.scan_date;
    const t = s.run_time ? new Date(s.run_time).toLocaleString() : '';
    const n = s.hits.length;
    const countCls = n === 0 ? 'count zero' : 'count';
    html += `<div class="scan-group">
      <div class="scan-header">
        <span class="date">${d}</span>
        <span class="time">${t}</span>
        <span class="${countCls}">${n} signal${n !== 1 ? 's' : ''}</span>
      </div>`;
    if (n === 0) {
      html += '<div class="empty">No BUY(dip) signals in this scan.</div>';
    } else {
      html += `<table>
        <tr>
          <th>Ticker</th><th class="num">Close</th><th class="num">Dist%</th>
          <th class="num">RSI</th><th class="num">ADX</th>
          <th class="num">Stop</th><th class="num">T1</th><th class="num">T2</th>
          <th class="num">Size</th><th>Validated</th>
        </tr>`;
      for (const h of s.hits) {
        let valHtml = '';
        if (h.validated === true) {
          valHtml = '<span class="badge ok">OK</span>';
        } else if (h.validated === false) {
          valHtml = `<span class="badge fail">FAIL</span><span class="val-reason">${h.validate_reason || ''}</span>`;
        } else if (h.validated_at) {
          valHtml = `<span class="badge unknown">ERR</span><span class="val-reason">${h.validate_reason || ''}</span>`;
        } else {
          valHtml = '<span class="badge unknown">—</span>';
        }
        if (h.validated_at) valHtml += `<br><span class="val-date">${h.validated_at}</span>`;
        html += `<tr>
          <td class="ticker">${h.ticker?.replace('.BK','') || '—'}</td>
          <td class="num">${fmt(h.close)}</td>
          <td class="num ${distClass(h.distPct)}">${fmt(h.distPct,1)}%</td>
          <td class="num">${fmt(h.rsi,0)}</td>
          <td class="num">${fmt(h.adx,0)}</td>
          <td class="num">${fmt(h.stop)}</td>
          <td class="num">${fmt(h.t1)}</td>
          <td class="num">${fmt(h.t2)}</td>
          <td class="num">${fmtInt(h.size)}</td>
          <td>${valHtml}</td>
        </tr>`;
      }
      html += '</table>';
    }
    html += '</div>';
  }
  $content.innerHTML = html;
}

async function load() {
  try {
    const res = await fetch('/api/scans');
    const data = await res.json();
    render(data.scans);
  } catch (e) {
    console.error('load failed', e);
  }
}

function connectSSE() {
  const es = new EventSource('/api/events');
  es.addEventListener('reload', () => load());
  es.onopen = () => {
    $status.textContent = 'live';
    $status.classList.add('live');
  };
  es.onerror = () => {
    $status.textContent = 'reconnecting…';
    $status.classList.remove('live');
  };
}

load();
connectSSE();
</script>

</body>
</html>"""

# --- Main --------------------------------------------------------------------

if __name__ == "__main__":
    _start_watcher()
    print(f"\n  Scan viewer running at http://localhost:{PORT}\n")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
