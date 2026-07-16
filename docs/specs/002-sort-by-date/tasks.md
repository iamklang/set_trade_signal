# Tasks — Sort Scans by Most Recent Date

**Feature ID:** 002-sort-by-date | Created: 2026-06-29
**Legend:** `[P]` = ทำขนานได้ · เรียงแบบ test-first

## Phase A — Tests First (🔴)
- [x] **T001** test: sort order ตาม scan_date desc, run_time desc ภายในวันเดียวกัน — AC-1, AC-2, AC-3

## Phase B — Implementation (🟢)
- [x] **T002** เปลี่ยน sort key ใน `_load_scans()` จาก `run_time` เป็น `(scan_date, run_time)` → ผ่าน T001

## Phase C — Verification
- [ ] **T003** รัน test suite ให้ผ่าน + เปิด viewer ตรวจด้วยตา

## Dependency Notes
- T002 ต้องทำหลัง T001 (test-first)
- T003 ต้องทำหลัง T002
