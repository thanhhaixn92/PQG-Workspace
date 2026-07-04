# Checkpoints — Hermes Local Stack V1

Branch: `feature/hermes-local-stack-v1`

Mỗi checkpoint chỉ tick khi:
- Backend tests pass (`cd backend && pytest -v`)
- Frontend tests pass (`cd frontend && npm test -- --run`)
- Lint pass (`cd frontend && npm run lint`)
- Build pass (`cd frontend && npm run build`)
- Manual smoke test pass

---

## CP0 Baseline Lock
- [ ] ADRs committed (`docs/adr/001` through `004`)
- [ ] Characterization tests pass (baseline recorded)
- [ ] Backend tests pass
- [ ] Frontend tests pass

---

## CP1 Schema
- [x] Migrations 0005-0011 up/down pass
- [x] Repository tests pass
- [x] Backup app.db created (`app.db.baseline`)

---

## CP2 TaskService
- [ ] TaskStateMachine transition tests pass
- [ ] Idempotency tests pass
- [ ] Follow-up behavior tests pass

---

## CP3 Legacy Adapter
- [ ] FE cũ vẫn chạy (gọi route cũ)
- [ ] Session submit format không đổi
- [ ] Hermes stream đúng format
- [ ] Approval flow đúng
- [ ] Audit đúng
- [ ] `USE_TASK_API=true` + characterization tests pass (so khớp CP0)

---

## CP4 Public API
- [ ] POST /api/tasks idempotent (same=200, diff=409)
- [ ] SSE events stream đúng thứ tự
- [ ] Cancel dừng Hermes run
- [ ] Approval gắn với action cụ thể
- [ ] Audit cho mọi endpoint

---

## CP5 Frontend Migration
- [ ] Task creation + streaming UI qua Task API
- [ ] Approval UI qua approval_id
- [ ] Task cancel từ UI
- [ ] Session history vẫn hiển thị
- [ ] 93 frontend tests pass
- [ ] `VITE_USE_TASK_API=false` fallback hoạt động

---

## CP6 Outbox Dispatcher
- [ ] Transaction atomicity (task + outbox cùng commit/rollback)
- [ ] Restart safety (pending rows được xử lý lại)
- [ ] No duplicate send (idempotency key)
- [ ] Dead letter khi max attempts

---

## CP7 Telegram Channel
- [ ] Signature sai → 401
- [ ] User không trong allowlist → 403
- [ ] Update retry → không tạo task trùng
- [ ] Callback token dùng lại → 409
- [ ] Token hết hạn → 410

---

## CP8 Model Fallback
- [ ] 429/quota → fallback → task succeeds
- [ ] Timeout/5xx → retry → fallback → succeeds
- [ ] 401/403 → dừng, no fallback
- [ ] Cooldown respected
- [ ] TaskRun ghi đúng attempt chain

---

## CP9 Skill Version
- [ ] Chỉ approved skills được inject vào context
- [ ] Draft skill không ảnh hưởng runtime
- [ ] Version history đầy đủ
- [ ] Audit cho mọi version mutation

---

## CP10 Cleanup (Release Sau)
- [ ] Legacy route metrics = 0 consumer
- [ ] `X-Deprecated: true` header active
- [ ] Code dead removed
