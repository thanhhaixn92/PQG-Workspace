---
name: verify-and-handoff
description: Verify approved Codex automation handoffs, update AI coordination files, and stop at Hermes state gates without starting CP6.
---

# verify-and-handoff

## Purpose

Antigravity acts as coordinator/verifier for approved handoff workflows.

## Required Reads

Read these files before doing anything:

- `AGENTS.md`
- `AI_TASK.md`
- `AI_STATE.json`
- `AI_HANDOFF.md`
- `AI_CHANGELOG.md`
- `AI_VERIFICATION.md`
- `AI_RISK_REGISTER.md`

## State Gate

Run only when all of these are true:

- `AI_STATE.json.next_agent` is `antigravity`
- `AI_STATE.json.lock` is `null`
- `AI_STATE.json.human_approval_required` is `false`

Stop immediately if any of these are true:

- `AI_STATE.json.state` is `CP5_COMPLETE` and `AI_STATE.json.next_agent` is `human`
- `AI_STATE.json.state` is `BLOCKED`
- `AI_STATE.json.human_approval_required` is `true`
- `AI_STATE.json.lock` is not `null`

## Locking

- Set `AI_STATE.json.lock` to `antigravity` while running.
- Release the lock when done.
- If verification is blocked, release the lock and update handoff files.

## Verification Scope

- Verify Codex changes with safe checks only.
- Update `AI_VERIFICATION.md` with commands and results.
- Update `AI_HANDOFF.md` with outcome and next state.
- Update `AI_RISK_REGISTER.md` if new risks are found.

## Hard Stops

- Never modify product code unless explicitly approved.
- Never start CP6 without human approval.
- Never commit, push, merge, deploy, reset, clean, delete, or modify forbidden files.
