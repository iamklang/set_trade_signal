# Implementation Plan — Sort Scans by Most Recent Date

**Feature ID:** 002-sort-by-date | Based on: spec.md, constitution.md | Created: 2026-06-29

> ตอบ **อย่างไร (how)** — tech stack, สถาปัตยกรรม, การตัดสินใจเชิงเทคนิค

## 1. Technical Context
- Language/Runtime: Python 3 (FastAPI + uvicorn)
- Frontend: embedded HTML/JS ใน `viewer.py`
- Testing: pytest

## 2. Architecture
ไม่มี component ใหม่ — เปลี่ยน sort key ใน `_load_scans()` ที่มีอยู่แล้ว

## 3. Project Structure
```
viewer.py          ← เปลี่ยน sort key (1 บรรทัด)
tests/
  test_viewer.py   ← เพิ่ม test sort order
```

## 4. Key Technical Decisions
| การตัดสินใจ | ทางเลือก | ที่เลือก | เหตุผล |
|------------|---------|---------|--------|
| Sort key | `run_time` เดี่ยว vs `(scan_date, run_time)` tuple | **`(scan_date, run_time)` desc** | ตรงกับ mental model เทรดเดอร์ — คิดเป็นวันซื้อขาย |
| Sort ที่ไหน | Backend vs Frontend | **Backend** | single source of truth — API คืนเรียงแล้ว |

## 5. Constitution Gate Check
- [x] Simplicity Gate — 1 จุดเปลี่ยน, ไม่เพิ่ม component
- [x] Test Gate — เขียน test ก่อน implement
- [x] Contract Gate — API `/api/scans` contract ไม่เปลี่ยน schema, เปลี่ยนแค่ลำดับ
- [x] UX Gate — ไม่มี state ใหม่ (loading/error/empty เดิมยังใช้ได้)

## 6. Non-Functional Notes
- Performance: ไม่มีผลกระทบ — sort tuple vs string เท่าๆ กัน

## 7. Linked Artifacts
- research.md / tasks.md
