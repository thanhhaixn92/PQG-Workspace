# ADR-002: Task = Unit Nghiệp Vụ, Session = Context Hội Thoại

**Ngày:** 2026-07-04
**Trạng thái:** Đã phê duyệt

## Context

Hệ thống hiện tại dùng `session` làm đơn vị chính: mỗi session có một workspace, lịch sử chat, và task_runs. Tuy nhiên, một session có thể chứa nhiều yêu cầu khác nhau:

- "Tổng hợp báo cáo tuần"
- "Tìm email liên quan"
- "Tạo lịch họp"
- "Chỉnh lại báo cáo"

Nếu session là task, không thể theo dõi riêng trạng thái từng việc, khó hủy một việc mà không ảnh hưởng hội thoại, và approval không biết thuộc hành động nào.

## Quyết định

Task là đơn vị nghiệp vụ có vòng đời riêng. Session là context hội thoại.

```
Session 1 ─── N Tasks
Task    1 ─── N Runs
Task    1 ─── N Events
Task    1 ─── N Actions
Task    1 ─── N Approvals
Task    1 ─── N Artifacts
```

- `tasks.session_id` = nullable (cho phép task từ cron/webhook không thuộc session)
- Task có trạng thái riêng: queued → running → waiting_approval → succeeded/failed/cancelled
- Follow-up khi task chưa done → event; khi task đã done → child task

## Hệ quả

- Phân tách rõ context và công việc
- Mỗi task có lifecycle, audit, approval riêng
- Task có thể cancel độc lập
- Task không session vẫn hoạt động (cron, webhook, API)
- Cần migration: thêm tasks table, điều chỉnh task_runs, thêm idempotency
