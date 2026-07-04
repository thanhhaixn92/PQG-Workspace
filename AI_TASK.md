# AI Task

## Task

Perform CP10 Cleanup of deprecated legacy APIs and establish deprecation headers.

## Current Checkpoint

- Current checkpoint: CP10 Cleanup (Complete).
- State: CP10_COMPLETE / V1 complete / awaiting final human review
- CP5, CP6, CP7, CP8, CP9, and CP10 are complete and preserved.

## Constraints

- Implement strictly CP10 Cleanup scope.
- Do not implement CP11+, auth expansion, deployment, vector search, or Excalidraw.
- Prefer backend-only changes; do not touch frontend unless CP10 validation requires it.
- Do not modify secrets, deployment config, billing config, production database settings, database files, or migrations.
- Do not auto commit, push, merge, deploy, reset, clean, or run destructive commands.
- Do not use dangerous automation flags.

## Done When

- Verify legacy route metrics show no active consumers (or write tests to check behavior).
- Add `X-Deprecated: true` response header to deprecated HTTP endpoints (e.g. legacy session routes).
- Dead code is removed only after explicit human approval.
- Focused backend tests cover all CP10 acceptance criteria.
- `AI_STATE.json` is valid JSON.
- Relevant backend tests pass.
- AI handoff/verification/changelog/risk files are updated.
