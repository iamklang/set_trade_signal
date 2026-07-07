# Implementation Plan — LINE Notify after Dip Scan

**Feature ID:** 003-line-notify | Based on: spec.md, constitution.md | Created: 2026-06-29

> ตอบ **อย่างไร (how)** — tech stack, สถาปัตยกรรม, การตัดสินใจเชิงเทคนิค

## 1. Technical Context
- Language/Runtime: Python 3, same venv (`~/.venvs/trading-dr`)
- HTTP client: `urllib.request` (stdlib) — ไม่ต้อง install dependency เพิ่ม
- Testing: pytest + unittest.mock

## 2. Architecture

```
alert.py
  └─ line_notify.py::send_line_push(text)
       └─ LINE Messaging API  POST /v2/bot/message/push
```

2 components: `line_notify.py` (LINE push logic) + integration point ใน `alert.py`

## 3. Project Structure
```
line_notify.py    ← NEW: send_line_push(text) function
alert.py          ← MODIFY: เรียก send_line_push() หลัง evaluate + macOS notify
tests/
  test_line_notify.py  ← NEW: unit tests
```

## 4. Key Technical Decisions
| การตัดสินใจ | ทางเลือก | ที่เลือก | เหตุผล |
|------------|---------|---------|--------|
| HTTP client | requests / httpx / urllib | **urllib.request** | stdlib, ไม่ต้อง install เพิ่ม; request เดียว ไม่ต้อง session/async |
| Module แยก vs inline | inline ใน alert.py / module แยก | **module แยก** | testable โดยไม่ต้อง import alert.py ทั้งหมด; reusable ถ้าจะใช้ที่อื่นภายหลัง |
| Credential storage | env var / .env file / config file | **env var** | เรียบง่าย, ปลอดภัย (ไม่ commit), launchd plist set ได้ |

## 5. Constitution Gate Check
- [x] Simplicity Gate — 2 components (line_notify.py + alert.py integration), ≤ 3
- [x] Test Gate — test ก่อน implement (mock HTTP)
- [x] Contract Gate — `send_line_push(text: str) -> bool` นิยามชัด
- [x] UX Gate — best-effort: ส่งไม่ได้ก็ log แล้วไปต่อ

## 6. Non-Functional Notes
- LINE Messaging API push message limit: 500/month (free plan) — เพียงพอสำหรับ daily alert
- Channel access token ต้องเป็น long-lived token จาก LINE Developers Console
- ข้อความ LINE text message จำกัด 5,000 characters

## 7. Linked Artifacts
- research.md / contracts/
