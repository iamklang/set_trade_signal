# Spec-Kit Templates (manual workflow)

โครงเปล่าสำหรับทำ Spec-Driven Development แบบ manual ตามแนว [github/spec-kit](https://github.com/github/spec-kit)

## ลำดับการใช้ (workflow)
| ขั้น | คำสั่ง spec-kit | ใช้ template | ได้ไฟล์ |
|------|----------------|-------------|---------|
| 1 | `/speckit.constitution` | `constitution.template.md` | `memory/constitution.md` |
| 2 | `/speckit.specify` | `spec.template.md` | `specs/NNN-name/spec.md` |
| ⭐ | `/speckit.clarify` | — (แก้ spec) | อัปเดต spec.md |
| 3 | `/speckit.plan` | `plan` + `research` + `data-model` + `quickstart` template | ไฟล์ใน `specs/NNN-name/` |
| 4 | `/speckit.tasks` | `tasks.template.md` | `tasks.md` |
| ⭐ | `/speckit.analyze` | — (ตรวจ consistency) | report |
| 5 | `/speckit.implement` | — | โค้ดจริง |

## วิธีเริ่ม feature ใหม่
```bash
mkdir -p specs/002-my-feature/contracts
# copy templates ที่ต้องใช้ แล้วแทนที่ {{PLACEHOLDER}}
```

## หลักสำคัญ
- spec.md = **what/why** เท่านั้น (อย่าใส่ how)
- plan.md = **how** (tech/architecture)
- constitution = ด่านตรวจคุณภาพทุกขั้น
- เขียนเทสต์ก่อน implement (test-first)
- contract คือ source of truth — เปลี่ยนทีต้อง sync ทุกฝั่ง

## ตัวอย่างจริง
ดู `specs/001-todo-app/` เป็นตัวอย่างที่กรอกครบทุกขั้น (Todo web app, React SPA + FastAPI, 2 repos)
