# Quyết định tìm kiếm tri thức có kiểm soát v1

**Ngày:** 2026-08-10
**Trạng thái:** Được Codex ủy quyền để triển khai lát nhỏ.

## Phạm vi

- Tìm cụm từ tất định trong `content` và `provenance` của các bản ghi tri thức
  thuộc đúng một nhiệm vụ.
- Chuẩn hóa khoảng trắng và so khớp không phân biệt hoa/thường bằng `casefold()`;
  không dùng AI, vector, FTS, tìm kiếm ngữ nghĩa hoặc dữ liệu/chỉ mục song song.
- Không migration, không dependency và không ghi dữ liệu hoặc audit cho lần tìm.

## Lọc chính sách trước khi trả dữ liệu

- Dùng duy nhất `evaluate_usability` của policy v1 hiện hành cho từng ứng viên.
- `official_search`, `analysis_input`, `legal_review`, `context_packaging` và
  `memory_query`: chỉ trả kết quả `usable`.
- `exploratory_search`: trả kết quả `partial_usable` hoặc `usable`, nhưng phải
  ghi rõ mức khả dụng; trong policy v1 hiện hành, kết quả có nguồn đã xác minh
  là `partial_usable`.
- Không trả nội dung của bản ghi `unusable`. Phân trang chỉ áp dụng sau khi đã
  so khớp và lọc chính sách.

## Hợp đồng tối thiểu

- `GET /api/dirap/work-items/{task_id}/knowledge-records/search?q=...&query_type=...&limit=...&offset=...`
- `q`: cụm từ không rỗng sau chuẩn hóa; tối đa 200 ký tự.
- `limit`: mặc định 20, tối đa 100; `offset`: mặc định 0.
- Mỗi kết quả gồm ID, nội dung rút gọn, provenance, lifecycle, bốn chiều gốc,
  mức khả dụng theo mục đích và trường khớp. Không trả dữ liệu từ nhiệm vụ khác.
- Phản hồi gồm tổng số sau lọc và thông tin phân trang. Không trả nội dung hay
  lý do chi tiết của các bản ghi bị loại.
