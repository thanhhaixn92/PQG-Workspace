# Quyết định chính sách khả dụng v1

**Ngày:** 2026-08-10
**Quyết định:** Codex chọn phương án C trong hồ sơ hòa giải v0.2.

## Quy tắc đã chốt

- `authority_status` tiếp tục là dữ kiện gốc: `none`, `regulatory`,
  `organizational`, `expert`, `derived`.
- Không dùng hoặc lưu nhãn `authoritative`. Chính sách khai báo trực tiếp tập
  giá trị thẩm quyền được chấp nhận theo từng mục đích.
- `overall_usability_state` là giá trị chỉ đọc, được tính mỗi lần truy vấn;
  không có cột, migration hay API ghi cho giá trị này.
- `official_search` và `legal_review` chỉ chấp nhận `regulatory` trong v1.
  `derived` không được dùng cho hai mục đích này cho tới khi có dữ kiện nguồn
  gốc, bằng chứng kế thừa và quy tắc kiểm chứng riêng.
- `analysis_input` chấp nhận `regulatory`, `organizational`, `expert` hoặc
  `derived`.
- Với các mục đích có yêu cầu `any`, tập chấp nhận gồm cả năm giá trị, kể cả
  `none`.
- Khi thuật toán chung mâu thuẫn với quy tắc của một mục đích cụ thể, quy tắc
  cụ thể được ưu tiên.
- `memory_query` trả `usable` khi `owner_acceptance_state=accepted`; các chiều
  còn lại không phải điều kiện chặn trong v1.

## Phạm vi triển khai được phép

Triển khai một phép tính thuần và API chỉ đọc giải thích khả dụng cho một bản
ghi tri thức, theo sáu mục đích chuẩn. Không triển khai tìm kiếm, truy vấn
agent, tự động đưa vào memory, AI, migration, hay thay đổi dữ kiện gốc.
