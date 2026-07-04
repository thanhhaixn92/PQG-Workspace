# Daily Usage - Hermes Local Stack

## Chay ung dung

```powershell
.\start-dev.ps1 -NoReload
```

Mo webapp tai dia chi script hien ra, mac dinh:

```text
http://localhost:5173
```

Tat moi tien trinh dev do script mo:

```powershell
.\stop-dev.ps1
```

## Chat hang ngay

1. Mo tab `Phien`.
2. Tao phien moi hoac chon phien cu.
3. Dam bao `Kiem tra he thong` bao Hermes san sang.
4. Nhap yeu cau va bam gui.
5. Neu refresh trang, lich su chat cua phien gan nhat se duoc tai lai tu SQLite.

## Quan ly phien

- Doi ten phien bang nut but chi trong tung dong phien.
- Luu tru phien bang nut archive. Day la soft archive, khong xoa du lieu that.
- `Don phien test` chi luu tru cac phien co ten bat dau bang `Smoke Test`.

## Phe duyet

Khi Hermes muon ghi bo nho, chay lenh, sua tep, hoac goi n8n, webapp se hien hop thoai `Can phe duyet`.

- `Cho phep mot lan`: chi cho hanh dong hien tai.
- `Cho phep trong phien`: cho phep loai hanh dong tuong tu trong phien hien tai, neu khong phai rui ro cao.
- `Tu choi`: khong thuc hien hanh dong.

Khong co `allow always` cho hanh dong rui ro cao.

## File editor

- Mo tab `Tep` sau khi chon phien.
- Mo tep trong workspace de chinh sua.
- Editor hien `Chua luu`, `Dang luu...`, `Da luu`, hoac `Loi luu`.
- Co the bam nut luu thu cong.
- Neu dong tep khi con dirty, UI se hoi xac nhan.

## Kiem tra nhanh

```powershell
.\check-dev.ps1
.\smoke-dev.ps1 -TimeoutSeconds 180
```

Ket qua mong doi:

- Backend OK.
- DB OK.
- Hermes `ready` hoac `mock`.
- Prompt smoke stream xong va co `done`.

## Loi thuong gap

- Backend khong ket noi: chay lai `.\start-dev.ps1 -NoReload`.
- Hermes chua san sang: kiem tra `backend\.env`, dong `HERMES_EXECUTABLE_PATH`.
- n8n chua cau hinh: co the bo qua neu chua dung automation.
- Cong 5173/8000 bi chiem: dung `.\stop-dev.ps1`, sau do chay lai script start.
