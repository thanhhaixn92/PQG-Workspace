# ADR-004: Transactional Outbox do Backend Sở Hữu

**Ngày:** 2026-07-04
**Trạng thái:** Đã phê duyệt

## Context

Khi task hoàn thành, hệ thống cần gửi notification đến các channel (Telegram, webapp). Có các phương án:

1. Backend gọi n8n ngay trong request lifecycle (dễ mất notification nếu crash)
2. n8n poll SQLite (phá vỡ policy boundary)
3. Transactional outbox do backend sở hữu, dispatcher push sang n8n

## Quyết định

Dùng transactional outbox pattern: backend ghi notification event vào SQLite trong cùng transaction với task update, sau đó background dispatcher đọc outbox và POST n8n webhook.

```
FastAPI cập nhật task + thêm outbox event (cùng transaction)
→ OutboxDispatcher poll pending rows
→ Claim bằng lease (UPDATE ... SET locked_at, locked_by)
→ POST n8n notification webhook
→ 2xx → status='sent'; 4xx → retry; 5xx → retry
→ Max attempts → dead_letter
```

## Hệ quả

- At-least-once delivery
- Restart backend không mất notification
- Retry không gửi trùng (nhờ idempotency key = event_id)
- n8n không đọc SQLite
- Cần background worker trong backend (poll interval 2s)
- Cần dead letter queue cho notification lỗi
