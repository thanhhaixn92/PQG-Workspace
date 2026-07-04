# ADR-001: FastAPI là Orchestrator Duy Nhất

**Ngày:** 2026-07-04
**Trạng thái:** Đã phê duyệt

## Context

Hermes Local Stack có nhiều thành phần: FastAPI backend, Hermes ACP agent, n8n workflow engine, SQLite database, và frontend webapp. Trong quá trình phát triển, có thể xu hướng để Hermes hoặc n8n tự do gọi nhau trực tiếp, dẫn đến:

- Policy boundary bị phá vỡ (approval, audit bị bypass)
- Khó xác định nơi giữ task state
- Vòng phụ thuộc: FastAPI → Hermes → n8n → FastAPI → Hermes
- Retry có thể tạo tác vụ trùng
- Approval bị phân tán
- Khó hủy task toàn bộ

## Quyết định

FastAPI là orchestrator duy nhất và policy boundary cho toàn bộ hệ thống.

- Mọi request từ frontend, Telegram, hay channel khác đều qua FastAPI
- Hermes ACP là "reasoning worker" — không gọi n8n trực tiếp
- n8n là "deterministic workflow worker" — không sở hữu task state, không gọi Hermes, không đọc SQLite trực tiếp
- n8n chỉ được gọi channel endpoint có giới hạn (kèm HMAC) và callback endpoint có chữ ký
- FastAPI giữ task state, approval, audit, idempotency

## Hệ quả

- Tập trung policy, approval, audit tại một điểm
- Dễ kiểm soát vòng đời task
- Dễ rollback và debug
- Thêm channel mới (Telegram, Slack, Email) không ảnh hưởng agent runtime
- Backend phải expose API cho n8n callback, nhưng limited scope
