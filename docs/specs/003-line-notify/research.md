# Research — LINE Notify after Dip Scan

**Feature ID:** 003-line-notify | Created: 2026-06-29

## R-1: HTTP client

| ตัวเลือก | ข้อดี | ข้อเสีย |
|---------|------|--------|
| **urllib.request (stdlib)** ✅ | zero dependency, เพียงพอสำหรับ single POST | verbose กว่า requests |
| requests | API สะอาด | ต้อง pip install เพิ่ม |
| httpx | async support | overkill สำหรับ single request |

**สรุป:** urllib — Simplicity Gate: ไม่เพิ่ม dependency สำหรับ HTTP call เดียว

## R-2: LINE Messaging API Push Message

**Endpoint:** `POST https://api.line.me/v2/bot/message/push`

**Headers:**
```
Content-Type: application/json
Authorization: Bearer {channel_access_token}
```

**Body:**
```json
{
  "to": "{userId}",
  "messages": [
    {"type": "text", "text": "..."}
  ]
}
```

**Response:** 200 = success, 400 = bad request, 401 = invalid token, 429 = rate limit

**Limits:**
- Text message max 5,000 chars
- Push messages: free plan 500/month, light plan 5,000/month
- Max 5 messages per request (เราใช้ 1)

## R-3: Environment Variables

| Variable | ค่า | ที่มา |
|----------|-----|------|
| `LINE_CHANNEL_TOKEN` | Channel access token (long-lived) | LINE Developers Console > Channel > Messaging API |
| `LINE_USER_ID` | userId ของตัวเอง | LINE Developers Console > Channel > Basic settings > Your user ID |

ทั้งสองไม่มีค่า default — ถ้าไม่ set ก็ skip LINE notification เงียบ

## Open Questions
- ไม่มี
