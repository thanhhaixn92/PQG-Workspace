# Hermes Local Stack - PRD

## 1. Tom Tat San Pham

Hermes Local Stack la tro ly van phong AI chay local, cho phep nguoi dung lam viec voi agent Hermes thong qua UI rieng. San pham tap trung vao chat streaming, thao tac file trong workspace, quan ly memory/skills, approval an toan, va automation qua n8n.

MVP khong nham lam he thong multi-user production. Muc tieu la mot local workstation assistant co the quan sat, ghi audit, va kiem soat hanh dong cua agent.

## 2. Nguoi Dung Chinh

- Mot nguoi dung ca nhan tren may local.
- User muon Hermes doc/sua file trong workspace, ho tro lap ke hoach, tao tai lieu, chay tac vu co kiem soat.
- User muon Antigravity trien khai va Codex review thay cho viec tu kiem tra tung chi tiet ky thuat.

## 3. Van De Can Giai Quyet

- Chat voi Hermes can streaming ro rang, co activity cua tool/terminal/file diff.
- File operations cua agent can gioi han trong workspace, tranh truy cap nham ra ngoai.
- Memory/skills can co quan ly ro, khong dua toan bo lich su hoi thoai vao context.
- Approval can phan biet hanh dong doc, ghi noi bo, va destructive/external.
- n8n can tich hop duoc nhung khong tro thanh cua hau bao mat.
- Qua trinh build can co checklist nghiem thu de Codex duyet ky thuat nhat quan.

## 4. Goals

- Tao UI chat voi Hermes qua ACP.
- Stream token va events realtime bang typed SSE.
- Quan ly sessions, task runs, memory, skills, files.
- Thuc thi approval policy va audit log.
- Gioi han file access vao workspace.
- Cho phep n8n workflow sidecar duoc goi co kiem soat.
- Tao bo test/eval de Codex review tung phase.

## 5. Non-Goals

- Multi-user auth.
- Cloud hosting.
- Public API.
- Agent tu tao tool moi khong qua review.
- Vector DB/graph DB trong MVP.
- Fine-tune model.
- Dong bo full conversation history tu Hermes state.db sang app.db.

## 6. User Stories MVP

### Session va Chat

- La user, toi tao session moi gan voi workspace path.
- La user, toi gui prompt va nhin thay token stream realtime.
- La user, toi thay tool call, terminal command, file diff, va plan update trong activity panel.
- La user, toi co the tiep tuc session cu.

### Approval

- La user, toi thay prompt approval khi agent muon ghi file, chay lenh, xoa file, hoac goi n8n.
- La user, toi co the allow once, allow for session, hoac deny.
- La user, toi khong bi hoi approval cho thao tac read an toan trong workspace.

### Files

- La user, toi xem file tree cua workspace.
- La user, toi mo va sua file bang Monaco.
- La user, noi dung duoc autosave co debounce va co dirty indicator.
- La user, agent khong the doc/ghi file ngoai workspace.

### Memory va Skills

- La user, toi tao/sua/tat/bat skill.
- La user, toi tao/sua/xoa memory entry.
- La user, toi co the xem de xuat memory/skill update tu curator truoc khi chap nhan.

### Automation

- La user, toi cau hinh n8n webhook local.
- La user, toi yeu cau Hermes kich hoat workflow n8n va phai phe duyet neu co data ra ngoai.

## 7. Functional Requirements

- Backend co `GET /health`.
- Backend co session CRUD toi thieu.
- Backend co prompt API va SSE events.
- Backend co file tree/read/write API.
- Backend co skills CRUD.
- Backend co memory CRUD.
- Backend co approval API.
- Backend ghi `audit_events` cho write/external/destructive actions.
- Frontend co chat, sessions, activity, approvals, files, memory, skills.
- DB migration reproducible.
- n8n config khong hardcode secret.

## 8. Non-Functional Requirements

- Local-first, offline-capable tru cac integration external.
- Startup backend khong crash neu Hermes chua cau hinh; phai tra error ro.
- SSE events la JSON hop le.
- Moi file path phai duoc resolve va validate.
- Test co the chay local bang command documented.
- UI khong bi treo khi stream error.
- Secrets khong commit vao source.

## 9. MVP Definition

MVP dat khi:

- Tao session va chat voi Hermes duoc qua UI.
- Token stream qua typed SSE.
- Approval flow hoat dong.
- File editor doc/ghi trong workspace an toan.
- Skills/memory CRUD co audit.
- Permission model duoc enforce.
- n8n sidecar goi duoc qua backend co approval.
- Codex review va approve cac phase theo checklist.

## 10. Post-MVP

- Diagram Mermaid -> Excalidraw.
- Search nang cao tren sessions/memory.
- Export report.
- Multi-workspace dashboard.
- Optional vector search.
- Optional multi-user auth.

