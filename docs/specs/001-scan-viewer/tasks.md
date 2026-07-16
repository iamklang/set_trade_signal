# Tasks — Scan Results Viewer

**Feature ID:** 001-scan-viewer | Created: 2026-06-28
**Legend:** `[P]` = parallelizable

## Phase A — Setup
- [ ] **T001** Install dependencies: `fastapi`, `uvicorn`, `watchdog`, `jinja2`

## Phase B — Implementation
- [ ] **T002** Create `viewer.py` with CSV parsing logic (glob + parse filenames for date/time)
- [ ] **T003** Add `/api/scans` endpoint returning JSON per contract
- [ ] **T004** Add SSE `/api/events` endpoint + watchdog file watcher
- [ ] **T005** Add `/` route serving embedded HTML template with table + SSE client

## Phase C — Validation
- [ ] **T006** Start server, verify latest scan shows in browser (AC-1)
- [ ] **T007** Verify historical scans grouped by date/time, newest first (AC-2)
- [ ] **T008** Run `scan_dip.py`, verify auto-refresh in browser (AC-3)
- [ ] **T009** Remove all CSVs temporarily, verify "no results" message (AC-4)
