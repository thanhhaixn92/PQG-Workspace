# G — Branch Governance Proof

Recorded: 2026-08-25 01:53:07 UTC+07:00

This non-runtime document is the bounded proof payload for Package G.

The target branch `pqg-workspace` requires a pull request and the canonical
`pqg/smoke` check. It does not require an approving review for the single-owner
repository, `pqg/preflight`, `pqg/smoke-full`, tracking integrity, signatures,
CODEOWNERS, a merge queue, or deployment environments. Force-push and branch
deletion are disabled.

The pull request carrying this file is intentionally outside the tracking
allowlist so that its required check executes full validation. This proof does
not change product runtime, provider behavior, credentials, state/checkpoint,
or F9.
