# Implementation Plan — Scan Results Viewer

**Feature ID:** 001-scan-viewer | Based on: spec.md, constitution.md | Created: 2026-06-28

## 1. Technical Context
- Language/Runtime: Python 3.11+ (existing venv `~/.venvs/trading-dr`)
- Backend: FastAPI + uvicorn
- Frontend: Vanilla HTML/CSS/JS (embedded in Python, no build step)
- Auto-refresh: Server-Sent Events (SSE) + watchdog filesystem watcher

## 2. Architecture

```
Browser <──SSE──> FastAPI server (viewer.py)
                     │
                     ├── GET /           → HTML page (Jinja2 template)
                     ├── GET /api/scans  → JSON array of all scan results
                     └── GET /api/events → SSE stream ("reload" on new CSV)
                              │
                     watchdog ──watches──> dip_scan_*.csv files
```

Single file `viewer.py` — server + watcher + embedded template.

## 3. Project Structure

```
trading_dr/
├── viewer.py          # NEW — the viewer server
├── dip_scan_*.csv     # existing scan outputs (read-only)
└── ...
```

## 4. Key Technical Decisions

| Decision | Alternatives | Chosen | Rationale |
|----------|-------------|--------|-----------|
| Server | Flask, static HTML | **FastAPI** | Async-native (SSE), minimal, fast |
| Auto-refresh | WebSocket, polling | **SSE** | One-way push, native browser API, simpler |
| Frontend | React, htmx | **Vanilla JS** | Single page, simple tables, zero build |
| File watch | polling, inotify | **watchdog** | Cross-platform, event-driven |
| Packaging | separate template files | **Embedded HTML** | One-file deploy, no path issues |

## 5. Constitution Gate Check
- [x] Simplicity Gate — 3 components: server, watcher, frontend
- [x] Test Gate — test CSV parsing + API response
- [x] Contract Gate — `/api/scans` JSON shape defined in contracts/
- [x] UX Gate — readable table, auto-refresh, clear timestamps

## 6. Non-Functional Notes
- Local only, no auth needed
- Startup: `~/.venvs/trading-dr/bin/python viewer.py`
- Default port 8050 (avoids conflict with common ports)

## 7. Linked Artifacts
- contracts/api.md — `/api/scans` response schema
