# Current Checkpoint

Last updated: 2026-07-04

## Checkpoint

CP10 - Cleanup.

## Status

CP5, CP6, CP7, CP8, CP9, and CP10 Cleanup are complete, verified, and closed.

- Legacy route metrics show no active consumers.
- `X-Deprecated: true` header is active.
- Dead code is retained (not removed) for fallback compatibility with human approval. All gates are complete.

## Goal

Perform cleanup of deprecated legacy APIs and establish deprecation headers.

## Context

CP10 focuses on the decommissioning of deprecated APIs. It requires verifying that legacy route metrics show no active consumers, adding the `X-Deprecated: true` header to all deprecated endpoints, and carefully removing dead code without breaking backwards compatibility.

## Constraints

- Keep existing legacy session routes working (marked as deprecated).
- Enforce `X-Deprecated: true` headers on all legacy endpoints.
- Do not remove any code without explicit human approval.

## Required Implementation Shape

- Apply `X-Deprecated: true` header to deprecated HTTP endpoints (e.g. legacy session routes).
- Add tests verifying deprecation headers and safe fallback behavior.
- Document metrics of legacy route usage if available, or write tests fordeprecation behavior.

## Done When

- CP10 checklist is complete.
- Focused CP10 backend tests pass.
- Project state documents the CP10 outcome.

## Review Gate

CP10 Cleanup has been verified and closed (`CP10_COMPLETE`). All checkpoints in Hermes Local Stack V1 are now complete.
