# PQG Workspace — Current Project Memory

> Mutable current snapshot. Live canon/state/source/evidence prevail. Historical receipts remain append-only in [PROJECT_CHANGELOG.md](PROJECT_CHANGELOG.md) and Git history.

## Memory protocol and authority

- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Record only current, decision-relevant facts with second-precision timestamps. Never retain secrets, raw databases/audit dumps, chain-of-thought or unnecessary sensitive data. Memory maintenance is non-recursive.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Current continuity reads [the live Master Plan](../implementation/PQG_WORKSPACE_REMEDIATION_MASTER_PLAN.md), [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) and this file; the changelog owns historical evidence. These files do not override canon, live state, source or newer receipt evidence.

## Live baseline, state and protected boundaries

- [2026-08-24 23:16:11 UTC+07:00][recorded_at] Repository: `thanhhaixn92/PQG-Workspace`; default branch: `pqg-workspace`; current full-validated source is E3 `b11120749a13334456ce409cd5ecab6a2b731bdc`. The following direct documentation child is a tracking-closeout candidate only; its tracking receipt never relabels source runtime validation as executing on the child.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`. F7 remains scoped PASS; F9 Data Egress remains **CLOSED / NOT APPROVED**; F remains deferred. No package receipt promotes state or checkpoint.
- [2026-08-24 23:16:11 UTC+07:00][recorded_at] Completed package history now includes A0, A1, A2, B, C, D, E1, E2-A, E2-C, E2-D, E2-E, P-TRACK, P-MEM and E3. E2 overall remains IN PROGRESS only because E2-B is BLOCKED-UPSTREAM; exact source SHAs, runs and historical payloads remain in the changelog/plan ledger.

## Latest completed package and active gate

- [2026-08-25 02:31:00 UTC+07:00][recorded_at] Supersession: post-E3 work is normalized in `docs/implementation/V22_FINAL_EVIDENCE_MATRIX.md` and `V22_FINAL_GATE_REPORT.md`. E4 source `04873a2…` retired legacy Hermes/ACP real-smoke and exact full Smoke `32764327655` passed, but E4 is **PARTIAL** because aggregate activity made four provider dispatches against the planned cap of three; remote provider compute/billing stop remains `NOT PROVEN`.
- [2026-08-25 02:31:00 UTC+07:00][recorded_at] G is PASS: `pqg-workspace` requires a PR and only `pqg/smoke`; force-push and branch deletion are disabled. Representative PR #2 passed full Smoke `32764969168` and merged. H1 merged in PR #3; latest source before this docs reconciliation is `b3a10eb…`, whose PR #5 full Smoke `32768141938` passed.

- [2026-08-24 19:03:27 UTC+07:00][recorded_at] P-TRACK is COMPLETE. SOURCE has exact `pqg/smoke-full=success` and canonical `pqg/smoke=success`; T1 has exact `pqg/tracking-integrity=success` and canonical `pqg/smoke=success`. Tracking-equivalence is not runtime execution on T1.
- [2026-08-24 19:14:52 UTC+07:00][recorded_at] P-MEM is COMPLETE. T2 `603fdd19139e5cd3c76797e6576c25a746f79e40` failed closed on shallow ancestry, then corrective SOURCE `0994a6b7077964bd57e2043657ea4f5cec52d320` completed exact full Smoke `32725628340` with `pqg/smoke-full=success` and canonical `pqg/smoke=success`.
- [2026-08-24 21:28:55 UTC+07:00][recorded_at] E2-C is COMPLETE: source `03d2869…` resolves `vite 8.2.2 -> postcss 8.5.26 -> nanoid 3.3.18`; push `32729774355` is the canonical source-status target and workflow_dispatch `32729794074` is corroborating full evidence.
- [2026-08-24 21:28:55 UTC+07:00][recorded_at] E2-D is COMPLETE: source `8e3f2fd…` retains jsdom `29.1.1` and resolves Undici `7.29.0`; push `32733392294` is the canonical source-status target and workflow_dispatch `32733404512` is corroborating full evidence.
- [2026-08-24 23:16:11 UTC+07:00][recorded_at] E2-E is COMPLETE: source `479c3399fd0867421fb7aa1245e74246f4ac9878` passed Linux full Smoke `32738509343` and Windows Sandbox `32738509351`; docs child `5fff3153493dfb5fde1410edcd28a9b54a9cc45f` later passed tracking-equivalence run `32739156748`. Canonical Linux source payload is **551 passed / 81 skipped / 2 warnings**; local Windows `549 / 83 / 2` remains local-only evidence.
- [2026-08-24 23:16:11 UTC+07:00][recorded_at] Latest completed package: **E3**. Source `b11120749a13334456ce409cd5ecab6a2b731bdc` pins official GitHub Actions to immutable SHAs under the approved bounded post-release security-fix exception: checkout `3d3c42e…`, setup-python `9191ea1…`, setup-node `1acbd4c…`; frontend CI is explicit Node `24.16.0` with npm global download cache while retaining `npm ci` and no `node_modules` cache.
- [2026-08-24 23:16:11 UTC+07:00][recorded_at] E3 exact-source receipts are Agent Preflight `32749299759`, Windows Sandbox `32749299689`, and full Smoke `32749299548`, all SUCCESS with exact `pqg/preflight=success`, `pqg/sandbox-windows=success`, `pqg/smoke-full=success`, and canonical `pqg/smoke=success`. Source Smoke recorded backend **551 passed / 81 skipped / 2 warnings**, frontend **54 files / 334 tests PASS**, lint/type-check/build/runtime/readiness/cleanup PASS, Node `24.16.0`, npm `11.13.0`; avoidable Node20-target action warnings were not observed on the E3 source executions.

## Open residuals and next action

- [2026-08-25 02:31:00 UTC+07:00][recorded_at] E2-B remains **BLOCKED-UPSTREAM** after recheck: Monaco `0.56.0` still ships bundled DOMPurify `3.4.8` in ESM/min artifacts and issue #5454 remains open. Current production audit is 2 moderate / 0 high / 0 critical. No consumer override, dedupe or dependency update was performed.
- [2026-08-25 02:31:00 UTC+07:00][recorded_at] H3 is **PARTIAL**: the repaired isolated runner produced AppShell dark/light/theme artifacts but no terminal receipt covers its full frozen matrix. H4 is **NOT RUN**: a further real-provider run would exceed the already-breached E4 request budget. H5/H6 do not promote state; final readiness is NO.

- [2026-08-24 19:25:16 UTC+07:00][recorded_at] E2-B B1 is **BLOCKED-UPSTREAM**: PQG locks Monaco `0.55.1`/DOMPurify `3.2.7`; latest stable Monaco `0.56.0` still ships bundled DOMPurify `3.4.8`. Consumer override/dedupe/npm-tree output cannot replace shipped code. Browser reachability is conditional through user-managed content in the lazy editor; sandbox/UTF-8/size controls are mitigations, not closure.
- [2026-08-24 23:16:11 UTC+07:00][recorded_at] E3 leaves pre-existing frontend React `act(...)` stderr warnings for H2 warning fix/classification and leaves legacy guarded `smoke-real` as **SKIPPED**, not PASS; E4 owns retirement/replacement of that legacy Hermes/ACP acceptance semantic.
- [2026-08-24 23:16:11 UTC+07:00][recorded_at] Next owned package is **E4 — NOT STARTED / CLOSED**. E4 provider/network/credential use requires fresh explicit human approval before any real request or credential access. G/H/F/F9 and state/checkpoint remain unopened; branch protection remains OFF until G. E2-B rechecks only on a newer stable Monaco release with actual ESM/min artifacts at the then-current safe DOMPurify floor.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Approval remains required for protected scope, including dependency/tool changes, providers/credentials/network, schema/migration, F9, deployment, branch protection, and state/checkpoint promotion.
