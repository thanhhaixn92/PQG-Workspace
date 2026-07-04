# V1 Local Release And Usage Mode Plan

## Goal

Preserve Hermes Local Stack V1 locally, clean non-release artifacts from the working tree, and create a separate V1 usage workspace for real end-user work.

## Current State

- Local commit: `17db211 Complete Hermes Local Stack V1`
- Local tag: `v1.0.0`
- Source package exists at: `workspace_outputs/release/hermes-local-stack-v1.0.0.zip`
- `AI_STATE.json` must remain `CP10_COMPLETE`
- Do not push, deploy, or change feature code.

## Tasks

1. Local release archive
   - Create external release folder:
     `C:\Users\dtron\Documents\Hermes-Releases\v1.0.0`
   - Copy:
     `C:\Users\dtron\Documents\Hermes\workspace_outputs\release\hermes-local-stack-v1.0.0.zip`
     to the external release folder.
   - Generate SHA256 checksum:
     `hermes-local-stack-v1.0.0.zip.sha256`

2. Artifact cleanup
   - Restore `.dev/dev-state.json` to `HEAD`; it is local runtime timestamp state.
   - Do not delete `workspace_outputs/`.
   - Add local-only ignores to `.git/info/exclude`:
     - `workspace_outputs/`
     - `.dev/dev-state.json`
   - Expected final repo state:
     - No tracked source changes caused by cleanup.
     - `AI_STATE.json` still `CP10_COMPLETE`.

3. V1 usage mode
   - Create external usage workspace:
     `C:\Users\dtron\Documents\Hermes-User-Work`
   - Create subfolders:
     - `sessions/`
     - `outputs/`
     - `scratch/`
   - Add:
     `C:\Users\dtron\Documents\Hermes-User-Work\README.md`
   - README must state:
     - This folder is for real post-V1 user work.
     - Do not store real user work in `AI_*`, checkpoint docs, or source code folders.
     - New Hermes sessions should use a workspace under `Hermes-User-Work\sessions\...`.
     - Bugs found during usage should be recorded separately as backlog, not patched directly into V1 release unless explicitly approved.

4. Verification
   - Run:
     - `git status --short`
     - `git rev-parse --short HEAD`
     - `git tag --list`
     - `python -m json.tool AI_STATE.json`
   - Verify:
     - HEAD is still `17db211`
     - tag `v1.0.0` exists
     - external release zip and checksum exist
     - `AI_STATE.json` is valid and still `CP10_COMPLETE`
     - no push/deploy/commit was performed unless explicitly requested later.

## Non-Goals

- Do not push to remote.
- Do not deploy.
- Do not modify feature code.
- Do not change `AI_STATE.json`.
- Do not delete user output files.
