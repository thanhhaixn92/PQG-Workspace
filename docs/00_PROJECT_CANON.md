# Hermes Local Stack - Project Canon

File nay la muc luc va nguon tham chieu chinh cho Antigravity va Codex trong qua trinh xay dung Hermes Local Stack.

## Bo Tai Lieu Chuan

1. [01_PRD.md](01_PRD.md) - Product Requirements Document.
2. [02_DATA_STORAGE_MODEL.md](02_DATA_STORAGE_MODEL.md) - Mo hinh du lieu, luu tru, ownership.
3. [03_EXECUTION_PRINCIPLES.md](03_EXECUTION_PRINCIPLES.md) - Nguyen tac thuc hien va engineering rules.
4. [04_SECURITY_PERMISSION_POLICY.md](04_SECURITY_PERMISSION_POLICY.md) - Bao mat, permission, approval, audit.
5. [05_ACCEPTANCE_EVALUATION.md](05_ACCEPTANCE_EVALUATION.md) - Tieu chi nghiem thu va danh gia.
6. [06_HANDOFF_REVIEW_PROTOCOL.md](06_HANDOFF_REVIEW_PROTOCOL.md) - Giao thuc ban giao Antigravity -> Codex.
7. [07_DECISION_LOG.md](07_DECISION_LOG.md) - Quyet dinh kien truc da chot.
8. [08_TEST_DATA_SCENARIOS.md](08_TEST_DATA_SCENARIOS.md) - Bo scenario test/eval mau.
9. [ANTIGRAVITY_IMPLEMENTATION_PLAN.md](ANTIGRAVITY_IMPLEMENTATION_PLAN.md) - Ke hoach trien khai theo phase.

## Thu Tu Uu Tien Khi Co Xung Dot

Neu cac tai lieu co noi dung xung dot, ap dung thu tu sau:

1. Yeu cau moi nhat cua nguoi dung.
2. `04_SECURITY_PERMISSION_POLICY.md`.
3. `01_PRD.md`.
4. `02_DATA_STORAGE_MODEL.md`.
5. `03_EXECUTION_PRINCIPLES.md`.
6. `ANTIGRAVITY_IMPLEMENTATION_PLAN.md`.
7. Cac tai lieu con lai.

## Vai Tro

- Antigravity: trien khai theo plan, cap nhat handoff sau tung phase.
- Codex: checker, reviewer, chay test, xac nhan acceptance criteria, yeu cau fix neu chua dat.
- User: chi can tham gia khi co quyet dinh ngoai plan, rui ro cao, credential, external publish, hoac thay doi pham vi.

## Nguyen Tac Canon

- Local-first.
- FastAPI la policy boundary.
- Hermes ACP la agent runtime boundary.
- SQLite app.db chi luu business metadata.
- Khong duplicate full conversation history tu Hermes state.db.
- Moi thao tac write/external/destructive phai co audit.
- External/destructive actions luon can human approval.
- Codex duoc duyet ky thuat trong pham vi plan, khong duoc duyet thay user cho rui ro cao.

