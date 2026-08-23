# Memory Hub — Local Pilot

## Mục tiêu

Cho một người dùng dùng Memory Hub local ổn định với dữ liệu `normal` và
`preference`. Không có auto-context, dữ liệu `sensitive`/`restricted`, hoặc
đồng bộ ra ngoài máy tính.

## Khởi động và kiểm tra

Tại thư mục gốc dự án:

```powershell
.\start-dev.ps1 -NoReload
.\check-memory-hub.ps1
```

Lệnh thứ hai chỉ xác nhận backend, Credential Manager và operator boundary;
không in token. Nếu báo thiếu role, tạo hoặc khôi phục credential theo
`MEMORY_HUB_CREDENTIAL_BOOTSTRAP.md`, rồi khởi động lại process liên quan.

## Luồng dùng hằng ngày

1. Mở frontend local và chọn tab **Memory Hub**.
2. Chọn đúng phạm vi: sở thích toàn cục, dự án, hoặc tác vụ. Không có chế độ
   xem tất cả phạm vi.
3. Với `preference`: tạo đề xuất, chọn **Xác minh**, rồi **Xác nhận kích hoạt**.
4. Với `normal`: tạo đề xuất; mục này chờ Codex review, không được tự kích hoạt.
5. Với legacy: xem trước theo ID, chọn từng mục, rồi xác nhận nhập. Legacy
   `memory_entries` không bị sửa.

## Backup và restore drill

Chạy trước pilot đầu tiên và định kỳ sau các thay đổi quan trọng:

```powershell
.\backup-memory-hub-drill.ps1
```

Lệnh tạo backup SQLite nhất quán với WAL qua backend, khôi phục một bản tạm,
chạy `integrity_check`, kiểm tra bảng Hub và xóa bản tạm. Backup gốc được giữ
nguyên; đường dẫn được in để người dùng lưu trữ theo quy trình local của mình.

## Khi có lỗi

| Triệu chứng | Cách xử lý |
| --- | --- |
| Không kết nối backend | Chạy `.\start-dev.ps1 -NoReload`, sau đó `.\check-memory-hub.ps1`. |
| Operator boundary bị từ chối | Kiểm tra frontend URL và `CORS_ORIGINS` trùng nhau, rồi restart local app. |
| Thiếu credential role | Dùng Credential Manager theo tài liệu bootstrap; không đặt token vào `.env` hoặc chat. |
| Không activate được normal | Đây là policy đúng: normal cần Codex review. |
| Restore drill thất bại | Không thay backup gốc; dừng pilot và giữ backup để kiểm tra. |

## Tiêu chí pilot đạt

- Người dùng hoàn tất một preference qua đủ hai bước review/kích hoạt.
- Người dùng tạo một normal proposal và thấy nó giữ ở `proposed`.
- Một import legacy đã chọn không thay đổi legacy source.
- `backup-memory-hub-drill.ps1` báo pass.
- Sau restart, records và lifecycle vẫn còn đúng.
