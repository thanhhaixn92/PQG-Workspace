# Checklist Kiểm Tra Hằng Ngày

Dùng checklist này sau mỗi lần chỉnh UX/runtime hoặc trước khi dùng PQG Workspace cho công việc thật.

## Khởi Động

1. Chạy `.\start-dev.ps1 -NoReload` từ thư mục gốc dự án.
2. Mở `http://127.0.0.1:5173`.
3. Kiểm tra panel runtime:
   - Backend: `Sẵn sàng`
   - Cơ sở dữ liệu: `Sẵn sàng`
   - Hermes: `Sẵn sàng` hoặc có hướng dẫn cấu hình rõ ràng
   - n8n: `Bỏ qua` hoặc `Cần cấu hình` nếu chưa dùng tự động hóa

## Trò Chuyện

1. Tạo hoặc chọn một phiên.
2. Gửi prompt ngắn, ví dụ: `Tóm tắt workspace hiện tại trong 5 ý.`
3. Kết quả mong đợi:
   - Tin nhắn của người dùng vẫn hiển thị.
   - Hermes stream phản hồi hoặc hiển thị `Hermes đang xử lý...`.
   - Nếu quá 30 giây, UI giải thích rằng model/provider có thể chậm hoặc đang chờ phê duyệt.
   - Nếu cần quyền, modal phê duyệt hiển thị hành động và mức rủi ro bằng tiếng Việt.
   - Sau khi hoàn tất, ô nhập được bật lại.
4. Refresh trình duyệt và xác nhận lịch sử chat vẫn còn.

## File Đầu Ra

1. Mở phiên đã tạo file.
2. Kết quả mong đợi:
   - Output `desktop-local-file` hiển thị bằng thẻ file, không hiện JSON thô.
   - Thẻ file hiển thị `Trong workspace` hoặc `Ngoài workspace`.
   - File text trong workspace có thể mở qua tab Tệp.
   - `.docx` và file nhị phân không bị mở như text; copy đường dẫn và mở bằng Word hoặc ứng dụng phù hợp.
   - Thẻ file hiển thị quality badge: `Có thể dùng`, `Cần rà soát`, `HTML chưa đạt`, `Thiếu nguồn`, `Sai vị trí lưu file`.
   - Nếu quality badge không phải `Có thể dùng`, thẻ hiển thị "Nên rà soát trước khi đăng/xuất bản".

## Nhật Ký Hoạt Động

1. Mở `Nhật ký hoạt động`.
2. Ở chế độ `Tóm tắt`, kết quả mong đợi:
   - Timeline được gom theo task.
   - Mỗi task có trạng thái, thời lượng, số công cụ và số lần phê duyệt khi có dữ liệu.
   - Raw payload, command, actor và approval id được ẩn.
3. Chuyển sang `Kỹ thuật`.
4. Kết quả mong đợi:
   - Raw payload, tham số tool, output terminal và target phê duyệt hiển thị để debug.

## Phê Duyệt

1. Mở một yêu cầu phê duyệt có sẵn hoặc tạo tình huống cần phê duyệt.
2. Kết quả mong đợi:
   - Hành động script/terminal/n8n rủi ro cao không có nút `Cho phép trong phiên`.
   - Modal giải thích khi nào nên cho phép.
   - Activity ghi rõ quyết định cho phép/từ chối.
   - Tool chỉ tiếp tục sau khi quyết định đã được ghi DB và audit.

## Dữ Liệu Cục Bộ Và Backup

1. Mở tab `Dữ liệu`.
2. Bấm `Tạo backup DB`.
3. Kết quả mong đợi:
   - Backup tạo file timestamp mới, không overwrite.
   - Backup dùng SQLite backup API nên nhất quán với WAL.
   - Không copy secret hoặc upload dữ liệu ra ngoài.

## Chất Lượng Nội Dung

1. Tạo một prompt viết bài báo, ví dụ: "Viết bài báo về tầm quan trọng của cảng biển".
2. Kết quả mong đợi:
   - Prompt nhận thêm hướng dẫn xuất bản (Tựa đề, Lead, Nguồn tham khảo).
   - File HTML đầu ra được kiểm tra chất lượng.
   - Thẻ file hiển thị quality badge tương ứng.
   - Activity timeline ghi `content.quality_check` với label dễ hiểu.
3. Nếu file có lỗi cấu trúc HTML, badge hiển thị `HTML chưa đạt`.
4. Nếu file thiếu nguồn, badge hiển thị `Thiếu nguồn`.
5. Nếu file lưu trong `backend/`, badge hiển thị `Sai vị trí lưu file`.

## n8n Optional

1. Nếu n8n chưa cấu hình, Runtime panel phải báo `Bỏ qua` hoặc `Cần cấu hình`, không crash.
2. Nếu đã cấu hình secret và workflow `echo` nằm trong allowlist:
   - Cần chọn phiên trước khi test echo.
   - Nút `Test echo n8n` xuất hiện trong Runtime panel.
   - Khi bấm, app yêu cầu phê duyệt một lần.
   - Sau khi duyệt, kết quả hiển thị trong panel và audit không lưu secret/raw body.

## Kết Quả Smoke Thủ Công Gần Nhất

- Ngày: 2026-07-03 (cập nhật quality gate V2 + publishing guidance)
- URL kiểm tra: `http://127.0.0.1:5173`
- Runtime: Hermes thật nếu `backend/.env` đã cấu hình; n8n optional
- Trạng thái tự động gần nhất:
   - Backend: `90 passed`
   - Frontend tests: `93 passed`
  - Type-check: passed
  - Build: passed
- Ghi chú: Vite vẫn có cảnh báo chunk lớn từ Mermaid lazy chunks; đây là cảnh báo không chặn vận hành hiện tại.

## Lệnh Xác Nhận

- Backend: `backend\.venv\Scripts\pytest.exe tests -v`
- Frontend type-check: `npm run type-check`
- Frontend tests: `npm run test -- --run`
- Frontend build: `npm run build`
- Source text check: dùng `rg` để tìm các mẫu mojibake phổ biến trong `frontend/src`, `backend/app` và `docs`; kỳ vọng không có kết quả.
