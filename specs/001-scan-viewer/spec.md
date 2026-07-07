# Feature Specification — Scan Results Viewer

**Feature ID:** 001-scan-viewer
**Status:** Draft
**Created:** 2026-06-28

> WHAT and WHY only — no HOW.

## 1. Problem & Why

Scan results (`dip_scan_*.csv`) are scattered CSV files that require opening
each one individually in a terminal or spreadsheet. There is no quick way to
see the latest signals, compare across dates, or spot recurring names. A
readable web view with auto-refresh removes friction from the post-close
review workflow.

## 2. Target Users
- The trader running `scan_dip.py` after SET close, reviewing which names fired.

## 3. User Stories
- **US-1:** As a trader I want to see the latest scan results in a browser so I
  can review signals without opening CSV files manually.
- **US-2:** As a trader I want to browse historical scan results by date so I
  can see which names have been recurring.
- **US-3:** As a trader I want the page to auto-update when a new scan finishes
  so I don't need to manually refresh.

## 4. Functional Requirements
- **FR-1:** The viewer reads all `dip_scan_*.csv` files from the project directory.
- **FR-2:** Results are displayed in a clean, readable table — one section per
  scan date, newest first.
- **FR-3:** Each table row shows: ticker, close, dist%, RSI, ADX, stop, T1, T2,
  size.
- **FR-4:** The scan timestamp (from filename) is shown as a section header so
  the user knows which run produced it.
- **FR-5:** The page auto-refreshes when new CSV files appear (no manual
  browser reload needed).
- **FR-6:** The viewer runs as a local server started with a single command.

## 5. Acceptance Criteria (testable)
- **AC-1 (US-1):** Starting the server and opening the URL shows the most
  recent scan result in a readable table.
- **AC-2 (US-2):** All historical scan CSVs appear grouped by date/time,
  newest first.
- **AC-3 (US-3):** Running `scan_dip.py` while the viewer is open causes the
  new result to appear without manual refresh.
- **AC-4:** If no CSV files exist, the page shows a clear "no scan results"
  message.

## 6. Out of Scope
- Alert log viewing (alert.py output) — future feature.
- Filtering/search within results.
- Mobile-optimized layout.
- Authentication or remote access.
- Editing or deleting scan results from the UI.

## 7. Clarifications
- None remaining.

## Review Checklist
- [x] Every user story has acceptance criteria
- [x] No "how" leaked in
- [x] All [NEEDS CLARIFICATION] resolved
- [x] Consistent with constitution
