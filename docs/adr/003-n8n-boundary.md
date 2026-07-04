# ADR-003: n8n Boundary

**Ngày:** 2026-07-04
**Trạng thái:** Đã phê duyệt

## Context

n8n là workflow engine cho các integration bên ngoài (Gmail, Calendar, Drive, Telegram). Có nguy cơ để n8n:

- Đọc SQLite trực tiếp (phá vỡ data encapsulation)
- Gọi Hermes trực tiếp (bypass policy, approval, audit)
- Sở hữu task state (tạo hệ thống state phân tán)
- Nhận Telegram message native (bypass FastAPI policy)

## Quyết định

n8n không sở hữu task state, không gọi Hermes, không truy cập database trực tiếp.

n8n chỉ được:
- Gọi channel endpoint có giới hạn (kèm HMAC/signature)
- Gọi callback endpoint có chữ ký (ví dụ: approval callback)
- Nhận lệnh workflow từ FastAPI
- Trả kết quả theo correlation ID

Telegram adapter chạy trên n8n bắt buộc phải gọi FastAPI. n8n không phải nguồn xác thực cuối cùng — FastAPI phải kiểm tra lại user, token, expiry.

## Hệ quả

- Policy boundary được giữ vững
- Notification outbox do backend sở hữu, không để n8n poll SQLite
- n8n telegram trigger chỉ normalize message rồi POST FastAPI
- Cần channel-service-token (shared secret FastAPI + n8n)
- Cần HMAC signature cho mọi request từ n8n
