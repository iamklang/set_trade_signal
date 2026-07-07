# Project Constitution — {{PROJECT_NAME}}

> หลักการกำกับการพัฒนา ทุก spec/plan/task ต้องสอดคล้องกับเอกสารนี้
> Version: 1.0.0 | Ratified: {{DATE}}

## Article I — Simplicity First
- เริ่มด้วยส่วนประกอบให้น้อยที่สุด (≤ 3 ส่วนหลัก)
- ห้าม over-engineer / เผื่ออนาคตแบบ speculative

## Article II — Test-First
- ทุก feature มี acceptance criteria ที่ทดสอบได้ก่อนเขียนโค้ด
- เขียนเทสต์ให้ "แดง" ก่อน แล้วจึง implement ให้ "เขียว"

## Article III — Clear Contracts
- ทุก interface (API, data model) นิยามชัดก่อน implement
- เปลี่ยน contract → อัปเดตเอกสาร + เทสต์พร้อมกัน

## Article IV — Observable & Honest
- error สื่อสารชัด ไม่กลืนเงียบ; สถานะระบบสังเกตได้

## Article V — User Experience Consistency
- พฤติกรรม UI สม่ำเสมอ (loading/error/empty state ครบ); feedback ทันที

## Quality Gates
- [ ] Simplicity Gate — ส่วนประกอบ ≤ 3? ไม่เผื่ออนาคตเกินจำเป็น?
- [ ] Test Gate — acceptance criteria ทดสอบได้ครบ?
- [ ] Contract Gate — API/data model นิยามชัดก่อน implement?
- [ ] UX Gate — loading/error/empty state ครบทุกหน้า?
