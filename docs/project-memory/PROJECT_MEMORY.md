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

## Open residuals and next action

- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Open owned work: E2-B is discovery-first and can be BLOCKED-UPSTREAM; E2-C and E2-D are selective dependency packages; E2-E first selects one reproducibility authority; E3 owns action/toolchain remediation; E4 requires fresh provider/credential/network authorization and native-GYO proof; G owns PR-first governance; H1-H6 are later gates. External-fork custom-status compatibility remains NOT RUN.
- [2026-08-24 19:14:52 UTC+07:00][recorded_at] Current action: this docs-only continuity closeout is a direct bounded child of full SOURCE `0994a6b…`; after its exact receipt, stop before E2-B. Any later correction follows full fail-closed validation and begins with a fresh exact-ref preflight.
- [2026-08-24 19:03:27 UTC+07:00][recorded_at] Approval remains required for protected scope, including dependency/tool changes, providers/credentials/network, schema/migration, F9, deployment, branch protection, and state/checkpoint promotion.
