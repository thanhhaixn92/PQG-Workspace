# First Real Chat

Tài liệu này giúp đưa Hermes Local Stack từ trạng thái “webapp đã mở” sang “chat stream hoạt động”.

## Cách A - Chạy Thử Ngay Bằng Dev Mock

Dùng cách này khi chưa cài Hermes thật hoặc chỉ muốn kiểm tra UI nhanh.

1. Tạo file cấu hình backend nếu chưa có:

```powershell
Copy-Item backend\.env.example backend\.env
```

2. Mở `backend\.env` và đặt:

```env
HERMES_DEV_MOCK=1
HERMES_EXECUTABLE_PATH=hermes
HERMES_ARGS=acp
```

3. Khởi động app:

```powershell
.\start-dev.ps1 -NoReload
```

4. Mở `http://localhost:5173`.

5. Tạo một phiên, chọn workspace, rồi gửi prompt.

Kết quả mong đợi:

- Panel `Kiểm tra hệ thống` hiển thị đang dùng mock.
- Chat stream câu trả lời mẫu.
- Nhật ký hoạt động có tool call mock và event hoàn tất.
- Ô nhập mở lại sau khi nhận `done`.

## Cách B - Kết Nối Hermes Thật

Dùng cách này khi đã cài Hermes và chạy `hermes setup` xong.

1. Mở `backend\.env`:

```env
HERMES_DEV_MOCK=0
HERMES_EXECUTABLE_PATH=C:\Users\dtron\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes-acp.exe
HERMES_ARGS=
```

Nếu Hermes nằm trong `PATH`, có thể dùng:

```env
HERMES_EXECUTABLE_PATH=hermes
HERMES_ARGS=acp
```

2. Khởi động lại app:

```powershell
.\stop-dev.ps1
.\start-dev.ps1 -NoReload
```

3. Mở `http://localhost:5173`.

Kết quả mong đợi:

- `Kiểm tra hệ thống` hiển thị Hermes sẵn sàng.
- Gửi prompt sẽ stream token hoặc hiển thị trạng thái Hermes đang xử lý.
- Nếu Hermes yêu cầu quyền, modal phê duyệt xuất hiện.
- Ô nhập mở lại sau khi task hoàn tất.

## Khi Hermes Trả Lời Chậm

Nếu backend vẫn sẵn sàng nhưng Hermes mất hơn 30 giây mới trả lời, nguyên nhân thường gặp là:

- model/provider đang chậm hoặc quá tải,
- phiên chat đã dài,
- Hermes đang chờ bạn phê duyệt quyền,
- prompt kích hoạt nhiều tool hoặc nhiều vòng suy luận.

Cách xử lý nhanh:

- Nhìn panel `Nhật ký hoạt động` để xem có đang chờ phê duyệt không.
- Nếu có modal phê duyệt, chọn `Cho phép một lần` hoặc `Từ chối`.
- Thử prompt ngắn hơn.
- Tạo phiên mới nếu phiên hiện tại đã quá dài.
- Nếu chỉ cần test UI, bật `HERMES_DEV_MOCK=1`.
- Nếu cần tốc độ thật, đổi model/provider trong Hermes bằng `hermes setup model`.

## Xử Lý Lỗi Nhanh

- `Hermes chưa cấu hình`: thêm `HERMES_EXECUTABLE_PATH` vào `backend\.env`, hoặc bật `HERMES_DEV_MOCK=1`.
- `Không tìm thấy Hermes`: đường dẫn executable sai hoặc Hermes chưa nằm trong `PATH`.
- `Hermes chưa khởi động được`: Hermes tồn tại nhưng không kết nối ACP trước timeout.
- `Model Hermes/Nous đang quá tải`: thử lại sau hoặc đổi model/provider nhanh hơn.
- `Mất kết nối với luồng sự kiện`: kiểm tra backend còn chạy tại `http://127.0.0.1:8000/health`.
- Port bị chiếm: chạy `.\stop-dev.ps1` rồi `.\start-dev.ps1 -NoReload`.
