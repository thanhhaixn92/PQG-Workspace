# P0-03 — Local Provenance and Restore Safety

**Priority:** P0  
**Risk class:** local process/data safety  
**PR lane:** Standard PR  
**Depends on:** P0-02 merged  
**Blocks:** P0-04 and final MVP gate

## 1. Goal

After this package, a valid `.dev/dev-state.json` must be sufficient to answer:

```text
Which repository?
Which exact source SHA?
Which backend PID and process start-time?
Which backend command / working directory / port / DB?
Which frontend PID and process start-time?
Which frontend command / working directory / port?
```

If those facts cannot be proven from state plus live OS inspection, the scripts must **not reuse, not kill, and not restore**.

## 2. Audited current gap

Current `start-dev.ps1` records only ports, PIDs and one started timestamp. It may accept an already-running HTTP service as reusable based on port/health alone.

Current `stop-dev.ps1` trusts a recorded PID if that PID exists and kills its process tree without verifying creation time or command identity.

Current `restore-local-data.ps1` correctly validates backup manifest/hash/SQLite integrity and stages replacement, but its default DB offline guard checks only fixed ports `8000` and `8100`; a backend on a dynamic port can still hold the target DB.

## 3. Planned files

- `start-dev.ps1`
- `check-dev.ps1`
- `stop-dev.ps1`
- `restore-local-data.ps1`
- `backend/tests/test_restore_local_data.py`

Add a narrow PowerShell helper only if reuse across these scripts cannot be kept simple. No new runtime service.

## 4. Proposed dev-state schema

Exact field naming may be adjusted during implementation, but the state must include equivalent non-secret facts:

```json
{
  "schemaVersion": 2,
  "repositoryRoot": "<canonical absolute path>",
  "sourceSha": "<40-hex git SHA>",
  "startedAt": "<ISO-8601>",
  "backend": {
    "pid": 1234,
    "processStartTime": "<ISO-8601>",
    "workingDirectory": "<canonical backend path>",
    "command": "<expected command identity, no secrets>",
    "executable": "<expected executable identity>",
    "port": 8000,
    "dbPath": "<canonical SQLite path>"
  },
  "frontend": {
    "pid": 5678,
    "processStartTime": "<ISO-8601>",
    "workingDirectory": "<canonical frontend path>",
    "command": "<expected command identity, no secrets>",
    "executable": "<expected executable identity>",
    "port": 5173
  }
}
```

Do not store `.env` values, credentials, tokens or provider secrets in dev-state.

## 5. Identity proof rules

### Reuse

An existing backend/frontend may be reused only when live OS inspection proves the recorded PID still has the recorded start-time and expected command/working-directory identity, the repository root matches, source SHA matches the current checkout, and backend DB binding matches the expected DB.

Health alone is insufficient.

If proof fails: choose a fresh available port for a newly launched process or fail closed according to the script's current mode. Do not silently adopt a foreign process.

### Kill

Before killing any recorded root PID, verify at minimum:

- PID exists;
- process creation/start time equals the recorded value;
- command/executable identity matches the recorded role;
- working directory/repository identity is consistent where available.

If verification fails, print a refusal and leave the process untouched. Do not remove state as if a safe stop succeeded.

### Restore

Before replacing a target DB:

1. identify whether dev-state declares that exact canonical DB path;
2. inspect the recorded backend PID/start-time/command and dynamic port;
3. inspect live processes/listeners sufficiently to prove the target DB is offline;
4. if the tool cannot prove offline status, refuse restore.

Preserve the current `-WhatIf`, explicit `-ConfirmRestore`, manifest/hash/integrity validation, safety copy, staging and rollback behavior.

## 6. Required negative tests

- stale dev-state with reused PID but different process start-time => no kill/reuse;
- command mismatch => no kill/reuse;
- repository/source SHA mismatch => no reuse;
- dynamic-port backend bound to target DB => restore blocked;
- target DB differs from recorded DB => no false proof from unrelated backend;
- missing/incomplete provenance fields => fail closed for destructive action;
- backup manifest/hash/integrity failure => no target mutation;
- prior restore marker conflict => no target mutation.

## 7. Required positive tests

- freshly started backend/frontend produce complete dev-state;
- `check-dev.ps1` reports source/process/port/DB proof distinctly from HTTP health;
- exact matching recorded process can be safely stopped;
- isolated offline DB restore succeeds after `-WhatIf` and `-ConfirmRestore`;
- safety backup remains as designed.

## 8. Validation environment

Because process creation time, command line, PID tree and PowerShell semantics are Windows-local concerns, canonical CI is necessary but not sufficient. Final package evidence should include an exact-SHA Windows-local validation in a clean checkout or equivalent controlled environment, without touching user data.

## 9. Stop / escalation conditions

Stop if implementation requires:

- recording secrets;
- broad process scanning unrelated to PQG identity proof;
- altering user DB/baseline during tests;
- new background service/daemon;
- schema/workflow/dependency changes.

## 10. Done criteria

P0-03 is done when dev-state provides complete non-secret provenance, reuse/kill/restore are all fail-closed on identity uncertainty, isolated negative tests cover stale/PID-reuse/dynamic-port cases, and exact-SHA Windows evidence plus canonical CI are recorded.
