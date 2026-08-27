# Controlled Local MVP Gate

**Gate status:** NOT RUN  
**Prerequisite:** P0-01, P0-02, P0-03 and P0-04 merged to `pqg-workspace`.  
**Rule:** after P0-04, stop feature/refactor work. Only gate evidence or bounded corrective PRs for a failing gate item are allowed until the gate reaches PASS.

## 1. Freeze the candidate SHA

After the four P0 PRs are merged, fetch default branch and record one exact candidate:

```text
candidate_default_sha = X
candidate_tree_sha = Y
```

All acceptance evidence must identify the source it actually validated. A PR workflow may validate a synthetic merge SHA; do not label a branch source head as validated if the runner checked out a different SHA.

Required evidence fields:

```text
source_head_sha
validation_sha
workflow_event
workflow_ref
run_id / job_id
local_checkout_sha
OS / environment
DB/workspace scope
result
known residuals
```

## 2. Mandatory gate checks

| Check | Requirement | PASS rule |
|---|---|---|
| Canonical CI | `pqg/smoke` on the final default candidate | success with validation SHA explicitly recorded |
| P0-01 stale decision | load -> stale/expire -> click approve | click-time preflight fails and **no approve POST** occurs |
| Native GYO journey | deterministic offline integrated acceptance | Work -> 2 conversations -> durable stream/source/proposal -> no mutation -> AP -> approve -> execute once -> restart PASS |
| Local provenance | exact-SHA Windows/local proof | dev-state proves repo/SHA/PID/start-time/command/port/DB/frontend |
| Stop safety | stale/PID reuse negative | identity mismatch => no process killed |
| Restore safety | isolated DB only | dynamic-port/in-use DB blocked; verified offline isolated restore PASS |
| Artifact atomicity | finalize-boundary failure injection | no committed artifact/audit success metadata and no orphan published file |
| Normal browser smoke | local loopback, provider-independent | primary shell/Work/GYO/AP flow usable without console/runtime blocker |
| Residual declaration | Monaco/baseline/provider limits | explicitly recorded; no false closure claim |

## 3. Data and environment restrictions

- Use only temporary/isolated SQLite DBs and workspaces for destructive/restore/failure tests.
- Do not overwrite `backend/app.db`, `backend/app.db.baseline`, user workspace outputs or real user files.
- No real provider/network/credential check is required for this gate.
- Do not change GitHub settings/workflows merely to make the gate pass.

## 4. PASS / FAIL logic

### PASS

The gate is PASS only when **all mandatory rows** above are supported by evidence tied to the final candidate SHA or by a documented validation SHA relationship that does not mislabel what was run.

Allowed narrow claim:

> `PQG Workspace controlled local MVP gate PASS on pqg-workspace@<X>.`

### FAIL

Any mandatory row that is `FAIL`, `BLOCKED`, `NOT RUN`, or supported only by an older source SHA keeps the gate FAIL/PARTIAL.

If a fix is needed:

```text
gate finding
-> one bounded corrective feature branch + PR
-> merge
-> candidate SHA changes
-> rerun affected evidence and canonical final gate on new SHA
```

Do not carry old PASS evidence across a source correction when the correction could affect that evidence.

## 5. What gate PASS does not mean

PASS does not automatically mean:

- production ready;
- cloud/multi-user ready;
- real provider/network ready;
- Monaco/DOMPurify upstream issue remediated;
- dependency backlog closed;
- five-person human usability complete;
- DIRAP v2.2 promoted;
- `AI_STATE.json` / checkpoint updated;
- F9 opened;
- deploy/publish approved.

Those are separate decisions and gates.

## 6. Opening P1-05 Foundation

Only after this gate is PASS may planning move to P1-05 Foundation contract refinement. The first pilot must use a narrow module such as `reports` or `review`, not Work/GYO, and must preserve the current React/Vite + FastAPI + SQLite architecture without introducing a general plugin platform.
