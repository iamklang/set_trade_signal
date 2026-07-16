# Tasks — LINE Notify after Dip Scan

**Feature ID:** 003-line-notify | Created: 2026-06-29
**Legend:** `[P]` = ทำขนานได้ · เรียงแบบ test-first

## Phase A — Contract
- [x] **T001** เขียน contract: `send_line_push(text: str) -> bool`

## Phase B — Tests First (🔴)
- [x] **T002** `[P]` test: send_line_push สร้าง HTTP request ถูก format (mock urllib) — AC-1
- [x] **T003** `[P]` test: send_line_push return False + log error เมื่อ API return 401 — AC-3
- [x] **T004** `[P]` test: send_line_push skip เงียบเมื่อไม่มี env var — AC-4
- [x] **T005** test: alert.py format message ถูกต้อง (มี signal / ไม่มี signal) — AC-1, AC-2

## Phase C — Implementation (🟢)
- [x] **T006** สร้าง `line_notify.py` → ผ่าน T002, T003, T004
- [x] **T007** เพิ่ม `--no-line` flag + เรียก `send_line_push()` ใน `alert.py` → ผ่าน T005

## Phase D — Verification
- [x] **T008** รัน test suite ทั้งหมดให้ผ่าน (9/9 passed)
- [ ] **T009** ทดสอบส่ง LINE จริง (ต้อง set env var)

## Dependency Notes
- T002-T004 ทำขนานได้
- T005 ต้องทำหลัง T006 (import line_notify)
- T006 → T007 → T008 → T009
