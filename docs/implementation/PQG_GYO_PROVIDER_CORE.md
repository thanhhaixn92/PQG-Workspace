# PQG Workspace — Trợ lý GYO Provider Core

## Trạng thái

`IMPLEMENTATION_IN_PROGRESS / PARTIAL`. Tài liệu này mô tả đường chạy GYO
mới; nó không thay đổi checkpoint v2.2 và không phải bằng chứng nghiệm thu
usability hoặc provider thật.

## Nguồn sự thật và ranh giới

- `app.db` tiếp tục sở hữu Work, conversation, Assistant turn/part, artifact,
  Action Package và metadata định tuyến.
- GYO là runner trung lập provider. GYO không có quyền ghi Work trực tiếp;
  mọi thay đổi vẫn đi qua `action_proposal` rồi Action Package được duyệt.
- Khóa provider chỉ ở Windows Credential Manager. SQLite chỉ lưu một tham
  chiếu mờ; REST, audit, SSE và manifest không trả hoặc ghi khóa.
- Hermes ACP không phải đường chạy của Assistant GYO. Mã legacy chỉ được giữ
  tạm để rollback kỹ thuật, không là fallback tự động.

## Provider và routing

Provider Core hỗ trợ `openai_responses` và `openai_compatible`. Mỗi provider
có thể có nhiều model profile với tier `fast`, `balanced`, `deep` hoặc
`vision`. Người dùng có thể chọn tay hoặc để router chọn deterministic:

1. Có attachment: yêu cầu model vision.
2. Prompt dài hoặc yêu cầu kế hoạch/phân tích/mã/đề xuất: deep.
3. Prompt ngắn: fast.
4. Còn lại: balanced.

Không có fallback âm thầm. Provider/model, route mode, selection reason và
fallback (nếu một adapter tương lai triển khai) được lưu theo assistant turn.
Provider/model bị retire không bị xóa khỏi provenance lịch sử.

## Memory và Skill

Context mặc định `suggest_only`: Memory Hub không vào chat. Chỉ mode
`active_work_memory` với Work và task cùng scope mới dùng record `active`,
không preference và không restricted. Manifest luôn nêu nguồn được dùng/bị
loại cùng lý do.

Các API learning yêu cầu evidence đã hoàn tất trong Work:

- `POST /api/gyo/learning/memory-candidates` tạo Memory Hub `proposed`.
- `POST /api/gyo/learning/skill-candidates` tạo Skill `draft`, disabled.

Không có activation, enable Skill hoặc mutation Work tự động.

## Điều chưa được coi là hoàn tất

- Chưa có provider thật được cấu hình hoặc credential được đưa vào source.
- Auto-propose theo lịch và subagent có ngân sách chưa được bật.
- Fidelity matrix/usability 5 người của v2.2 vẫn phải được kiểm chứng riêng.
