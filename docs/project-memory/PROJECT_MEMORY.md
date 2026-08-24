# PQG Workspace — Current Project Memory

> Mutable current snapshot. Live canon/state/source/evidence prevail. Historical receipts remain append-only in [PROJECT_CHANGELOG.md](PROJECT_CHANGELOG.md) and Git history.

## Memory protocol and authority

- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Record only current, decision-relevant facts with second-precision timestamps. Never retain secrets, raw databases/audit dumps, chain-of-thought or unnecessary sensitive data. Memory maintenance is non-recursive.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Current continuity reads [the live Master Plan](../implementation/PQG_WORKSPACE_REMEDIATION_MASTER_PLAN.md), [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) and this file; the changelog owns historical evidence. These files do not override canon, live state, source or newer receipt evidence.

## Live baseline, state and protected boundaries

- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Repository: `thanhhaixn92/PQG-Workspace`; default branch: `pqg-workspace`; current tracking baseline is T1 `42b16fcb2394528f0b73ebb2812a4c8ff5274953`, whose parent is full-validated SOURCE `2ac0e83184e891bd61f5543084b5d26868e10636`.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] State/checkpoint remain `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`. F7 remains scoped PASS; F9 Data Egress remains **CLOSED / NOT APPROVED**; F remains deferred. No package receipt promotes state or checkpoint.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] A0, A1, A2, B, C, D, E1 and E2-A are completed package history; E2 overall remains in progress. Exact source SHAs, runs and payloads are retained only in the changelog/plan ledger.

## Latest completed package and active gate

- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Latest completed package: **P-TRACK**. SOURCE has exact `pqg/smoke-full=success` and canonical `pqg/smoke=success`; T1 has exact `pqg/tracking-integrity=success` and canonical `pqg/smoke=success`. Tracking-equivalence is not runtime execution on T1.
- [2026-08-24 19:14:52 UTC+07:00][recorded_at] Latest completed package: **P-MEM**. T2 `603fdd19139e5cd3c76797e6576c25a746f79e40` failed closed on shallow ancestry, then corrective SOURCE `0994a6b7077964bd57e2043657ea4f5cec52d320` completed exact full Smoke `32725628340` with `pqg/smoke-full=success` and canonical `pqg/smoke=success`. This stronger recovery validates the normalized documentation tree; no T2.5 correction exists.
- [2026-08-24 20:00:38 UTC+07:00][recorded_at] Latest completed package: **E2-C**. Source `03d2869…` resolves `vite 8.2.2 -> postcss 8.5.26 -> nanoid 3.3.18`; canonical full Smoke `32729794074` has exact-source `smoke-full=success` and final `pqg/smoke=success`. E2 overall remains in progress; this does not promote state/checkpoint or F9.
- [2026-08-24 20:38:18 UTC+07:00][recorded_at] Latest completed package: **E2-D**. Source `8e3f2fd…` retains jsdom `29.1.1` and resolves its Undici test chain at `7.29.0`; canonical full Smoke `32733404512` has exact `pqg/smoke-full=success` and final `pqg/smoke=success`. E2 overall remains in progress; this does not promote state/checkpoint or F9.

## Open residuals and next action

- [2026-08-24 19:25:16 UTC+07:00][recorded_at] E2-B B1 is **BLOCKED-UPSTREAM**: PQG locks Monaco `0.55.1`/DOMPurify `3.2.7`; latest stable Monaco `0.56.0` still ships bundled DOMPurify `3.4.8`. Consumer override/dedupe/npm-tree output cannot replace shipped code. Browser reachability is conditional through user-managed content in the lazy editor; sandbox/UTF-8/size controls are mitigations, not closure.
- [2026-08-24 19:25:16 UTC+07:00][recorded_at] Open owned work: E2-C and E2-D are selective dependency packages; E2-E first selects one reproducibility authority; E3 owns action/toolchain remediation; E4 requires fresh provider/credential/network authorization and native-GYO proof; G owns PR-first governance; H1-H6 are later gates. E2-B rechecks only on a newer stable Monaco release with actual ESM/min artifacts at the then-current safe DOMPurify floor. External-fork custom-status compatibility remains NOT RUN.
- [2026-08-24 20:38:18 UTC+07:00][recorded_at] Next exact action: stop before separately gated E2-E. E2-B remains blocked; do not open E2-E/E3/E4/G/H/F/F9 or mutate state/checkpoint without fresh approval.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Approval remains required for protected scope, including dependency/tool changes, providers/credentials/network, schema/migration, F9, deployment, branch protection, and state/checkpoint promotion.
