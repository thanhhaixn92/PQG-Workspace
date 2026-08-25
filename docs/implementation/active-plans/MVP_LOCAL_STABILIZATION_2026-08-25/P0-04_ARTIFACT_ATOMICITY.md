# P0-04 — Artifact Atomicity

**Priority:** P0  
**Risk class:** **highest data-integrity risk in the four-package path**  
**PR lane:** Standard PR  
**Depends on:** P0-03 merged  
**Blocks:** final MVP gate

## 1. Goal

Close the DB/filesystem split-success failure window in current idempotent artifact workflows without turning the package into a global transaction-layer refactor.

The package must remain narrow around:

- managed text-file creation;
- document import;
- report creation;
- the shared audit/idempotency commit behavior strictly required to make those flows atomic with respect to their DB metadata.

Do not broaden to unrelated repositories/services unless current source proves the same helper change is unavoidable.

## 2. Audited failure window

At planning base, the workflow is effectively:

```text
claim idempotency operation
  -> COMMIT claim intentionally
publish file to managed filesystem
insert artifact / validation DB rows
log audit event
  -> log_audit_event defaults to COMMIT
finalize idempotency operation
  -> finalize_operation COMMIT
mark completed
```

If the audit commit succeeds and `finalize_operation()` then raises, the exception path can roll back only the current transaction, not the already committed artifact/audit rows. The finally block can delete the file. Result: DB may say an artifact/audit event exists while the file is gone and the operation claim is not completed.

## 3. Transaction design constraint

Keep `claim_operation()`'s initial commit. That commit is intentional so competing requests observe the `processing` claim before filesystem side effects begin.

After the file has been successfully published, use **one narrow DB transaction owner** for:

```text
artifact row
+ structural validation row(s)
+ audit event
+ transition operation_claim from processing -> completed
= one commit
```

A minimal implementation may add opt-in `commit=False` behavior to existing audit/finalize helpers and perform one explicit commit in the artifact workflow. Exact shape must be chosen from current source, but default behavior for unrelated callers should remain unchanged unless separately audited.

## 4. Planned files

Expected narrow scope:

- `backend/app/services/security_artifact_create.py`
- `backend/app/services/security_artifact_import.py`
- `backend/app/repositories/idempotency_repository.py` only if a non-committing finalize option/helper is needed;
- `backend/app/services/audit.py` only if the existing `commit=False` seam is not already sufficient at exact implementation SHA;
- `backend/tests/test_artifacts.py`.

No schema migration is planned.

## 5. Implementation sequence

For each in-scope filesystem workflow:

1. claim operation and keep current committed `processing` visibility;
2. validate inputs/quota and publish the file with create-only semantics;
3. begin/continue one DB transaction for metadata;
4. insert artifact and validation rows;
5. write audit event with no intermediate commit;
6. update the same operation claim to `completed` with no intermediate commit;
7. commit once;
8. only after commit set local `completed=True` and return success.

On any exception before step 7:

- rollback the metadata/audit/finalization transaction;
- mark the already-committed operation claim failed using the current failure policy;
- remove the published file in `finally`;
- return/raise current fail-closed API behavior.

Do not use compensating deletes as a substitute for transaction rollback of DB metadata.

## 6. Mandatory failure-injection tests

Inject failures at least at these boundaries:

- after filesystem publish but before DB metadata commit;
- after artifact/validation insert;
- after audit insert but before idempotency finalization commit;
- inside finalization before the single commit.

For each failure prove:

- no committed artifact row remains;
- no committed structural validation row remains;
- no committed success audit event remains;
- published file is removed;
- operation claim is not incorrectly `completed`;
- existing failed/retry semantics remain deterministic.

The most important regression is: **force finalize failure after audit logic and prove that neither the artifact/audit DB rows nor the file survive as a split success.**

## 7. Positive/idempotency tests

- normal create/import/report succeeds and records file + metadata + validation + audit + completed claim;
- same key/same payload returns existing completed result according to current API semantics;
- same key/different payload remains conflict;
- exactly one artifact/file exists after success;
- validation and audit behavior remain unchanged except commit ownership.

## 8. Explicit non-goals

- no global `aiosqlite` connection/autocommit redesign;
- no transaction abstraction framework;
- no schema migration;
- no change to unrelated action-package execution transaction semantics;
- no change to filesystem sandbox/quota/type-validation policy;
- no broad refactor of all idempotency callers.

## 9. Validation order

1. targeted failure-injection artifact tests;
2. full `test_artifacts.py`;
3. adjacent idempotency/audit focused tests if helper signatures change;
4. backend test suite subset required by repo policy;
5. canonical PR `pqg/smoke`;
6. post-merge controlled-local-MVP gate — **no feature/refactor package may start before the gate result**.

## 10. Stop / escalation conditions

Stop and re-plan if the narrow fix cannot be achieved without:

- migration;
- global transaction layer change;
- broad public helper behavior change;
- filesystem semantics change outside in-scope workflows;
- user data/baseline mutation.

## 11. Done criteria

P0-04 is done only when failure injection proves the DB/file/idempotency split-success window is closed, normal idempotent behavior remains intact, canonical CI passes, and the PR is merged. Immediately after merge, feature/refactor work stops and `MVP_GATE.md` is executed on one exact default SHA.
