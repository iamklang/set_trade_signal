# Research — Sort Scans by Most Recent Date

**Feature ID:** 002-sort-by-date | Created: 2026-06-29

## R-1: Sort key strategy

| ตัวเลือก | ข้อดี | ข้อเสีย |
|---------|------|--------|
| **`(scan_date, run_time)` tuple desc** ✅ | เรียงตามวันซื้อขายก่อน, ภายในวันเดียวกันเรียง run ล่าสุดก่อน; ทั้งสองค่าเป็น ISO string sort ตาม lexicographic ได้เลย | ถ้ารัน scan วันเก่าทีหลัง จะไม่ขึ้นบนสุด (ยอมรับได้ — ตรงกับ intent) |
| `run_time` เดี่ยว (ปัจจุบัน) | ง่าย, scan ล่าสุดที่รันขึ้นก่อนเสมอ | ไม่ตรง mental model — วัน 06-26 อาจขึ้นก่อน 06-27 ถ้ารันทีหลัง |

**สรุป:** ใช้ tuple sort — ตรงกับ Simplicity Gate (เปลี่ยน 1 บรรทัด) และ UX Gate (พฤติกรรมคาดเดาได้)

## Current Implementation

`viewer.py` line 99:
```python
scans.sort(key=lambda s: s["run_time"], reverse=True)
```

`scan_date` = string `"2026-06-26"`, `run_time` = ISO timestamp `"2026-06-29T20:58:12"`
ทั้งสองเป็น lexicographically sortable

## Open Questions
- ไม่มี
