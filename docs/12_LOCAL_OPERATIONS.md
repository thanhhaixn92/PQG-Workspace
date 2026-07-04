# Local Operations

Tai lieu nay gom cac lenh van hanh local can dung hang ngay.

## Start

```powershell
cd C:\Users\dtron\Documents\Hermes
.\start-dev.ps1 -Fresh
```

Ket qua mong doi:

- Script in URL frontend de mo app.
- Backend chi bind `127.0.0.1`.
- Frontend duoc cau hinh dung `VITE_API_BASE_URL`.
- Trang thai process duoc ghi vao `.dev\dev-state.json`.

## Check

```powershell
.\check-dev.ps1
```

Script se kiem tra:

- `backend\.venv`
- `frontend\node_modules`
- `backend\.env`
- backend `/health`
- backend `/api/runtime/status`
- frontend URL
- trang thai Hermes mock/real va n8n

## Smoke Test

```powershell
.\smoke-dev.ps1
```

Script se kiem tra luong runtime toi thieu:

- backend health
- runtime status
- tao session
- gui prompt
- doc SSE den khi co `done`

Neu dang bat `HERMES_DEV_MOCK=1`, smoke test phai thay token stream mau.
Neu dang dung Hermes that, smoke test se xac nhan backend co the gui prompt va nhan ket thuc stream.

## Hermes Doctor Check

Tu phien ban co `auth_expired`, backend tu dong chay `hermes doctor --json` truoc khi cho phep gui prompt:

- **Khi doctor OK** → preflight `ready`, prompt duoc phep gui.
- **Khi doctor fail** → preflight `auth_expired`, backend tra ve HTTP 503 va huong dan chay `hermes auth`.
- **Khi doctor timeout** (8s) → preflight `auth_expired` nhu fail.

Ban co the kiem tra thu cong:

```powershell
hermes doctor --json
```

Preflight đoctor check chay trong cac truong hop:
- Goi `POST /api/sessions/{id}/prompt` (submit prompt)
- Goi `POST /api/runtime/smoke` (smoke check)
- Khong chay khi goi `GET /api/runtime/status` (de tranh lam cham UI).

## Stop

```powershell
.\stop-dev.ps1
```

Script chi tat cay process do `start-dev.ps1` ghi lai trong `.dev\dev-state.json`.
Neu backend/frontend da chay san truoc do, script se khong tu y tat process ngoai project.

## First Chat

Neu chua co Hermes that, dung mock:

```env
HERMES_DEV_MOCK=1
HERMES_EXECUTABLE_PATH=hermes
HERMES_ARGS=acp
```

Neu da co Hermes ACP executable, dung runtime that:

```env
HERMES_DEV_MOCK=0
HERMES_EXECUTABLE_PATH=hermes
HERMES_ARGS=acp
```

Sau do chay:

```powershell
.\start-dev.ps1 -Fresh
.\check-dev.ps1
```

## Troubleshooting

- Backend khong len: kiem tra `backend\.venv` va port backend script da in.
- Frontend khong len: kiem tra `frontend\node_modules` va port frontend script da in.
- Hermes missing: bat `HERMES_DEV_MOCK=1` de test UI truoc, hoac sua `HERMES_EXECUTABLE_PATH`.
- SSE mat ket noi: kiem tra backend `/health` va refresh trang.
- n8n chua cau hinh: co the bo qua neu chua dung automation.

## Output Files

- Nen tao file Word, script tam va tai lieu dau ra trong workspace cua phien hoac thu muc output rieng.
- Khong nen dung `backend\` lam noi luu ket qua cong viec hang ngay, vi thu muc nay la ma nguon backend.
- Neu Hermes tao nham file trong `backend\`, hay di chuyen thu cong sang workspace/output sau khi kiem tra noi dung.
