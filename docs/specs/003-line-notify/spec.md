# Feature Specification — LINE Notify after Dip Scan

**Feature ID:** 003-line-notify
**Status:** Draft
**Created:** 2026-06-29

> อธิบาย **อะไร (what)** และ **ทำไม (why)** — ไม่ระบุ **อย่างไร (how)**

## 1. Problem & Why
ปัจจุบัน `alert.py` แจ้งเตือนผ่าน macOS notification เท่านั้น — เห็นเฉพาะตอนนั่งหน้า Mac
เทรดเดอร์ต้องการรับแจ้งเตือนผ่าน LINE บนมือถือด้วย เพื่อไม่พลาดสัญญาณ BUY(dip)
หลังตลาดปิด โดยเฉพาะเวลาไม่ได้อยู่หน้าจอ

## 2. Target Users
- เทรดเดอร์ที่ใช้ alert.py ผ่าน launchd หลัง SET ปิด (16:35 ICT)

## 3. User Stories
- **US-1:** ในฐานะเทรดเดอร์ ฉันต้องการรับข้อความ LINE สรุปผล alert หลัง alert.py ทำงานเสร็จ เพื่อดูสัญญาณบนมือถือได้ทันที
- **US-2:** ในฐานะเทรดเดอร์ เมื่อไม่มีสัญญาณ ฉันก็ต้องการรับ LINE แจ้งว่า "ไม่มีสัญญาณ" เพื่อรู้ว่า alert รันสำเร็จ (ไม่ใช่ hang/fail เงียบ)
- **US-3:** ในฐานะเทรดเดอร์ ถ้า LINE ส่งไม่ได้ (token ผิด, network down) ต้องไม่กระทบการทำงานหลักของ alert.py — แจ้ง error ใน log แล้วไปต่อ

## 4. Functional Requirements
- **FR-1:** หลัง alert.py ประเมินทุก symbol เสร็จ ระบบต้องส่ง LINE push message ไปยัง userId ของผู้ใช้ (1:1 กับ bot)
- **FR-2:** ข้อความเป็น plain text สรุป: จำนวนสัญญาณ, รายชื่อ ticker ที่ fired พร้อม close/stop/T1/T2/size
- **FR-3:** กรณีไม่มีสัญญาณ ให้ส่งข้อความแจ้งว่าไม่มีสัญญาณวันนี้
- **FR-4:** credential (channel access token, user ID) ต้องอ่านจาก environment variable — ห้าม hardcode
- **FR-5:** LINE notification เป็น best-effort — ถ้าส่งไม่ได้ให้ log error แล้ว continue (ไม่ crash, ไม่เปลี่ยน exit code)
- **FR-6:** สามารถปิด LINE notification ได้โดยไม่ set env var (graceful skip)

## 5. Acceptance Criteria (ทดสอบได้)
- **AC-1 (US-1):** เมื่อ alert.py มี 2 signals fired → LINE message มีรายชื่อ ticker 2 ตัวพร้อม trade plan
- **AC-2 (US-2):** เมื่อ alert.py ไม่มี signal → LINE message แจ้ง "ไม่มีสัญญาณ"
- **AC-3 (US-3):** เมื่อ LINE API return error (401/500) → alert.py ยังจบ exit code 1 ตามปกติ + log error message
- **AC-4 (FR-4):** เมื่อไม่ set env var LINE_CHANNEL_TOKEN/LINE_USER_ID → skip LINE notification เงียบ (ไม่ error)
- **AC-5 (FR-6):** flag `--no-line` ปิด LINE notification ได้

## 6. Out of Scope
- Flex Message / rich card format
- LINE notification จาก scan_dip.py (เฉพาะ alert.py)
- Webhook / reply message (ใช้ push เท่านั้น)
- Interactive LINE bot (reply, menu, richmenu)

## 7. Clarifications
- ไม่มี — scope ชัดเจนจากคำตอบผู้ใช้

## Review Checklist
- [x] ทุก user story มี acceptance criteria
- [x] ไม่มี "how" หลุดเข้ามา
- [x] เคลียร์ทุก [NEEDS CLARIFICATION] แล้ว
- [x] สอดคล้องกับ constitution
