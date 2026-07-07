# Feature Specification — Sort Scans by Most Recent Date

**Feature ID:** 002-sort-by-date
**Status:** Draft
**Created:** 2026-06-29

> อธิบาย **อะไร (what)** และ **ทำไม (why)** — ไม่ระบุ **อย่างไร (how)**

## 1. Problem & Why
ปัจจุบัน viewer.py แสดง scan results เรียงตาม `run_time` (เวลาที่รันสคริปต์)
ไม่ใช่ `scan_date` (วันซื้อขายที่ scan) — ทำให้เมื่อรันซ้ำหลายรอบในวันเดียว
ผลลัพธ์เรียงปนกันโดย scan วันเก่าๆ อาจเด้งขึ้นมาเพราะรันทีหลัง

ผู้ใช้ต้องการเห็นข้อมูลเรียงตาม **วันซื้อขายล่าสุดก่อน** — ถ้ามีหลาย run
สำหรับวันเดียวกัน ให้จัดกลุ่มรวมกันหรือแสดง run ล่าสุดสุดก่อน (ภายในวันเดียวกัน)

## 2. Target Users
- เทรดเดอร์ที่ใช้ scan viewer ผ่านเบราว์เซอร์ดูสัญญาณ BUY(dip) ประจำวัน

## 3. User Stories
- **US-1:** ในฐานะเทรดเดอร์ ฉันต้องการเห็นผลสแกนเรียงจากวันซื้อขายล่าสุดก่อน เพื่อดูสัญญาณวันนี้ได้ทันทีโดยไม่ต้องเลื่อนหา
- **US-2:** ในฐานะเทรดเดอร์ เมื่อมี scan หลาย run สำหรับวันเดียวกัน ฉันต้องการเห็น run ล่าสุดก่อน เพื่อดูผลที่อัปเดตที่สุด

## 4. Functional Requirements
- **FR-1:** ผลสแกนบนหน้าเว็บต้องเรียงลำดับตาม `scan_date` จากล่าสุดไปเก่าสุด (primary sort)
- **FR-2:** เมื่อ `scan_date` เท่ากัน ให้เรียงตาม `run_time` จากล่าสุดไปเก่าสุด (secondary sort)
- **FR-3:** API endpoint `/api/scans` ต้องส่งข้อมูลกลับมาตามลำดับเดียวกัน

## 5. Acceptance Criteria (ทดสอบได้)
- **AC-1 (US-1):** เมื่อมี scan 3 ไฟล์ (date: 06-24, 06-25, 06-26) → API คืนลำดับ 06-26, 06-25, 06-24
- **AC-2 (US-2):** เมื่อมี scan 2 ไฟล์ที่ scan_date เดียวกัน (06-26) แต่ run_time ต่างกัน → ไฟล์ที่ run_time ใหม่กว่าแสดงก่อน
- **AC-3:** เมื่อมี scan วัน 06-26 (run เมื่อ 06-29) กับ scan วัน 06-27 (run เมื่อ 06-28) → 06-27 แสดงก่อน 06-26 (แม้ run_time ของ 06-26 จะใหม่กว่า)

## 6. Out of Scope
- การจัดกลุ่ม (grouping/collapsing) หลาย run ในวันเดียวกันให้เหลือ 1 กล่อง
- การเพิ่ม UI controls (dropdown/toggle) ให้เลือกเรียงแบบอื่น
- Pagination หรือ infinite scroll

## 7. Clarifications
- ไม่มี — scope ชัดเจน

## Review Checklist
- [x] ทุก user story มี acceptance criteria
- [x] ไม่มี "how" หลุดเข้ามา
- [x] เคลียร์ทุก [NEEDS CLARIFICATION] แล้ว
- [x] สอดคล้องกับ constitution
