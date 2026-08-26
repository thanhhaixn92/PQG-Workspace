# PQG Workspace - Project Canon v2.2

File nay la muc luc va nguon tham chieu san pham cho PQG Workspace. Dieu phoi
coding-agent hien hanh theo Issue #13 va root `AGENTS.md`; Antigravity va cac
handoff cu chi la tham chieu lich su/compatibility, khong phai active route.
Runtime tro ly hien hanh la GYO qua `GyoOrchestrator`; Hermes/ACP chi con la
identifier ky thuat hoac compatibility/historical path, khong phai fallback cua
runtime hien hanh.

## Bo Tai Lieu Chuan

1. [01_PRD.md](01_PRD.md) - Product Requirements Document.
2. [02_DATA_STORAGE_MODEL.md](02_DATA_STORAGE_MODEL.md) - Mo hinh du lieu, luu tru, ownership.
3. [03_EXECUTION_PRINCIPLES.md](03_EXECUTION_PRINCIPLES.md) - Nguyen tac thuc hien va engineering rules.
4. [04_SECURITY_PERMISSION_POLICY.md](04_SECURITY_PERMISSION_POLICY.md) - Bao mat, permission, approval, audit.
5. [05_ACCEPTANCE_EVALUATION.md](05_ACCEPTANCE_EVALUATION.md) - Tieu chi nghiem thu va danh gia.
6. [06_HANDOFF_REVIEW_PROTOCOL.md](06_HANDOFF_REVIEW_PROTOCOL.md) - giao thuc
   Antigravity -> Codex lich su/compatibility, khong phai active routing.
7. [07_DECISION_LOG.md](07_DECISION_LOG.md) - Quyet dinh kien truc da chot.
8. [08_TEST_DATA_SCENARIOS.md](08_TEST_DATA_SCENARIOS.md) - Bo scenario test/eval mau.
9. [implementation/CURRENT_CHECKPOINT.md](implementation/CURRENT_CHECKPOINT.md) - checkpoint hien hanh.
10. `../AI_STATE.json` va `../PROJECT_STATE.md` - trang thai trien khai hien hanh.
11. [ANTIGRAVITY_IMPLEMENTATION_PLAN.md](ANTIGRAVITY_IMPLEMENTATION_PLAN.md) - tai lieu lich su, khong con la nguon quyet dinh v2.2.

## Thu Tu Uu Tien Khi Co Xung Dot

Neu cac tai lieu co noi dung xung dot, ap dung thu tu sau:

1. Yeu cau hien hanh ro rang cua nguoi dung, kem rang buoc platform va an toan.
2. `AGENTS.md`.
3. `PROJECT_STATE.md`, `AI_STATE.json`, va
   `implementation/CURRENT_CHECKPOINT.md`.
4. Product canon, security policy, va data model.
5. Current source, contracts, va focused tests.
6. Project Memory.
7. Historical handoffs, plans, chat, va evidence.

## Vai Tro

- **Codex Desktop**
  - sole repository implementation writer cho repository-changing packages;
  - local filesystem/shell/Git worktree actor;
  - technical decision authority trong approved scope;
  - co the commit/push feature branch va quan ly authorized package PR metadata;
  - khong merge protected PR neu chua co separate authority.
- **ChatGPT Web**
  - GitHub-connected research/audit/evidence/independent review actor;
  - thuc hien supported GitHub-side operations;
  - khong claim local shell/filesystem execution;
  - hand local/repository-changing work cho Codex.
- **GitHub**
  - canonical source, branch, PR, CI va merge-history authority.
- **User**
  - cung cap product intent;
  - cung cap explicit approval chi khi platform/repository/current policy yeu
    cau protected approval.

## Nguyen Tac Canon

- Local-first.
- FastAPI la policy boundary.
- `GyoOrchestrator` provider-neutral la runtime boundary cua Tro ly GYO sau FastAPI.
- SQLite `app.db` so huu Work, conversation va Assistant turns hien thi cho nguoi dung.
- Legacy Hermes/ACP state, neu con ton tai tu cai dat cu, khong duoc GYO doc, sua, dong bo hoac dung lam fallback.
- Lop MCP chi dung allowlist da cau hinh; mutation Work chi qua Action Package sau user approval.
- n8n la sidecar loopback tuy chon, khong chan checkpoint v2.2.
- Moi thao tac write/external/destructive phai co audit.
- External/destructive actions luon can human approval.
- Codex duoc duyet ky thuat trong pham vi plan, khong duoc duyet thay user cho rui ro cao.
- Admin boundary v2.2 chi chung minh mot request tuong tac qua giao dien local duoc cho phep, voi actor do server gan. Loopback, Origin va Fetch Metadata khong phai bang chung mat ma ve su hien dien cua con nguoi va khong phan biet duoc mot local process co du quyen.
- CapabilityRegistry ma GYO/model thay duoc khong chua Foundation/provider/Module/privacy/permission/restore/admin-Skill capabilities. Capability bi cam hoac khong biet phai fail closed voi `capability_not_found` truoc approval flow.

