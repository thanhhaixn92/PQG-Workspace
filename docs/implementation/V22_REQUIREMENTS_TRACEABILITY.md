# V2.2 Requirements Traceability

Updated: 2026-08-15. Gate: `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS` / `PARTIAL`.

Status meanings: `PASS` has reproducible implementation and test/runtime evidence; `PARTIAL` lacks part of the required evidence; `FAIL` is a confirmed contract violation; `NOT RUN` has not been executed. Human evidence is never inferred from automated tests.

| Requirement | PRD / decision source | Implementation / API / UI | Test or runtime evidence | Status |
|---|---|---|---|---|
| app.db owns user-visible Work conversations | PRD 1, ADR-008 | migrations 0025/0028; Assistant thread/turn/part repositories | backend conversation/Assistant suites; isolated restart UAT | PASS |
| Hermes state remains internal | PRD 5, ADR-008 | Hermes client boundary; no state.db adapter | code inspection; bounded real-Hermes restart recovered app.db turns | PASS |
| Exact nine-tool Hermes MCP allowlist | ADR-010 | `app/mcp/server.py` | `test_hermes_mcp_surface_is_exact_allowlist` | PASS |
| Work update is proposal-only | PRD 7, ADR-010 | `propose_work_update`; Action Package API | MCP + action-package focused regression | PASS |
| Action Package idempotency/exactly-once | PRD 7 | create/approve/execute APIs and operation claims | action-package regression; isolated proposal/package/executor UAT | PASS |
| Persistent summary requires approval | Security Policy; ADR-010 | `save_work_context_summary` pre/post scope checks | allow/deny/archive race regression | PASS |
| Memory Hub never auto-injects | PRD / Canon | governed Memory Hub API; context pack excludes it | context-pack and Memory Hub regression | PASS |
| Three data layers remain distinct | PRD / storage model | legacy memory, Memory Hub, Knowledge Records | schema/API regression | PASS |
| n8n is optional and loopback-only | ADR-009 | webhook validation/settings | n8n focused tests; no live external call required | PASS |
| Release version is 2.2.0 | PRD release contract | backend/frontend/lock/README | `test_release_version_is_consistent` | PASS |
| Theme is globally reachable/persistent | PRD UX | App Shell global theme toggle; `hermes.theme` | AppLayout Vitest; browser toggle + reload persistence | PASS |
| Responsive/focus/reduced motion | Acceptance 5.1 | App Shell/ContextDrawer CSS and focus controls | AppShell + Accessibility batches PASS at all breakpoint edges, reduced motion, Escape/focus restore and 320px reflow; actual Chrome zoom 200% PASS in isolated `v22-brandzoom-20260815-0900`; full cross-product remains incomplete | PARTIAL |
| Assistant attachment IDs are scoped to managed Work artifacts | PRD Assistant; Blueprint M3 | `AssistantTurnCreateRequest.attachment_artifact_ids`; user artifact parts; deterministic context priority | attachment scope/order/binary/retry focused regression | PASS |
| Retry preserves prompt and attachments without a second user turn | PRD Assistant lifecycle | Assistant retry query + artifact-part recovery | `test_assistant_attachments_are_scoped_ordered_and_preserved_on_retry` | PASS |
| Seven structured part types are produced in their applicable flows | PRD Assistant structured output | Assistant response writer, ACP filtered tool summaries, user artifacts, proposals, approval provenance, errors | backend focused structured-part tests; bounded real-Hermes proposal/package evidence | PASS |
| ACP output never persists raw tool arguments, terminal output, secrets or paths | Security Policy | filtered `consume_read_only_parts`; read-only Assistant boundary | safe proposal diagnostics + focused tool-result assertion + bounded real-Hermes runner | PASS |
| Proposal provenance creates one approval part without affecting package hash | PRD Action Package | optional `source_proposal_part_id`; same-scope validation; approval part append | proposal/package provenance and idempotency regression | PASS |
| Review remains a projection and decides at source lifecycle | PRD Review | Review Inbox calls Skill/Knowledge/Memory Hub/Action Package APIs directly | frontend focused lifecycle projection tests; backend lifecycle suites | PASS |
| Review deep link opens, focuses and highlights the source item | PRD Review navigation | `#review/{source}:{id}` + `useReviewTarget` + source data attributes | type-check/component coverage; browser evidence pending | PARTIAL |
| Shared UI primitives and split Assistant/Work components | Blueprint Design system | AppShell/PageHeader/StatusBadge/MetricCard/AsyncSection/EmptyState/ErrorState/ConfirmDialog; AssistantTurn/TurnPartRenderer/ActionProposalCard/PhaseCard/ArtifactList/ApprovalItem | focused extracted/consumer tests; type-check/lint/build | PASS |
| Dead Memory Hub helpers cannot register a tenth MCP tool | Security Policy; ADR-010 | Memory Hub MCP module contains undecorated loopback helpers only | exact-nine regression imports helper module first | PASS |
| Isolated end-to-end Work journey | Acceptance 4 | temp SQLite/workspace, `uat-codex-` | strict mock UAT: attachment/context/parts, succeeded package, exact mutations/attempts, cancel/retry, restart, archive guards | PASS |
| Bounded real-Hermes flow | Acceptance 4 | isolated backend and managed test data | `output/playwright/v22-batched-20260815-075743/real-hermes-final.log`: prompt/source/retry/proposal/no-preapproval-mutation/package/exactly-once/restart/late-output PASS; ACP mapping ready and cancel outcome `cancelled` | PASS |
| Fidelity matrix complete | Acceptance 5.1 | `V22_FIDELITY_LEDGER.md`; five-batch runner | five final batches PASS with 62 screenshots; true browser zoom 200% PASS with native Chrome evidence; full screen×state×viewport cross-product remains incomplete | PARTIAL |
| Product branding distinguishes app from runtime | Product owner decision 2026-08-15 | browser title, App Shell/product eyebrows, README/operating docs and FastAPI display title use `DIRAP Local Workbench`; assistant navigation uses `Trợ lý Hermes`; technical package/API/DB/env/schema/credential identifiers retained | `test_release_version.py` branding assertions; AppLayout Vitest; isolated Chrome title/App Shell screenshot at actual zoom 200% | PASS |
| Five-person usability >=4/5 | Acceptance 5.1 | `V22_USABILITY_PROTOCOL.md` | deferred post-v2.2 by product owner; no agent/mock substitution | NOT RUN |

Promotion rule: do not change coordinated state/checkpoint files to `DIRAP_V22_VALIDATED` while any required technical row remains `PARTIAL/NOT RUN`. Human usability is explicitly deferred hậu v2.2 but remains recorded as `NOT RUN`, not silently converted to PASS.
