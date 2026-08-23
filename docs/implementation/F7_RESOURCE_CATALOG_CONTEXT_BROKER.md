# F7 Resource Catalog + Context Broker

## Status and scope

F7 is an explicitly approved protected security/data-access slice for PQG Workspace. It introduces a server-side Resource Catalog and Context Broker for Trợ lý GYO while preserving the overall checkpoint `DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`.

F7 does **not** open F9 Data Egress. It does not authorize web-search queries, connector sends, upload/export, new network destinations, provider/credential changes, deployment, migration/schema changes, retention/delete changes, or checkpoint promotion.

## Hard invariant

The model-visible selection pipeline is:

```text
discover metadata
  -> SECURITY FILTER
  -> deterministic relevance/ranking
  -> hydrate authorized content
  -> byte-bounded context pack
  -> existing GYO provider boundary
```

**SECURITY FILTER MUST RUN BEFORE RELEVANCE/RANKING.**

A resource descriptor that fails authorization must not be passed to ranking, model selection, hydration, or provider context. Denied resource IDs, titles, backend locators and content must not be copied into model-visible catalog/context output.

## Resource classes

F7 currently brokers these local resource kinds:

- selected Work metadata and plan summary;
- Workspace task summary for the selected Work;
- selected Work conversation history;
- registered managed artifacts;
- explicitly enabled, Work/task-scoped active Memory Hub records;
- active approved knowledge when the Work allows `approved_library`;
- approved and enabled Skills when the Work allows `approved_library`.

Discovery is metadata-only. Filesystem content and record bodies are loaded only after authorization and ranking, with fail-closed revalidation before hydration.

## Sensitivity and trust classes

Sensitivity:

- `public`
- `internal`
- `sensitive`
- `restricted`

Trust:

- `canonical_user_data`
- `verified_knowledge`
- `derived_text`
- `external_unverified`
- `agent_generated_draft`

`restricted` resources are denied before ranking. Trust metadata is provenance/context metadata; it does not make provider/GYO-generated text trusted instructions. Provider/GYO output remains untrusted at the FastAPI boundary.

## Never-catalog resources

The following are outside the model resource catalog/context boundary:

- credentials, environment values and API keys;
- raw audit records;
- arbitrary filesystem paths or backend-only locators;
- raw `app.db` access/content;
- chain-of-thought or internal reasoning;
- foreign Work/Conversation/Memory resources;
- restricted Memory Hub records;
- lifecycle-ineligible knowledge/memory/skills.

## Compatibility surfaces

`backend/app/services/context_broker.py` is the F7 model-context policy boundary.

`backend/app/services/assistant_context.py` is a compatibility facade that delegates context construction to the broker. It must not grow a second independent selection policy.

`/api/assistant/context-manifest` remains a browser-facing provenance/diagnostic compatibility surface. Its `retrieved`/`included` groups come from the broker-built context pack. Browser-visible `accessible` metadata is not provider context and must not be treated by clients as model ranking evidence or authorization authority.

## Validation evidence

Pre-code F7 receipt:

- trigger commit: `3f9b254ed152f59e0d5fa8b3b4545a0b09dd1a52`
- Agent Preflight Run ID: `32666700014`
- result: `pqg/preflight=success`
- preflight reported clean checkout and pre-edit `diff --check exit: 0`.

F7 implementation commits:

- `84abd1aaea5c36af98fd7bcf7d1cbc9d47ee333d` — initial security-first broker implementation;
- `efe0a35aaf8d80b6187e63dda4cc7d47c1ece388` — compatibility fix preserving the Memory-scope exclusion contract.

The initial implementation run at `84abd1aa...` failed backend validation and is superseded by the correction; it is not PASS evidence.

Authoritative source-validation evidence is Smoke Test Run ID `32667595588` on exact HEAD `efe0a35aaf8d80b6187e63dda4cc7d47c1ece388`:

- committed-diff formatting check: PASS;
- backend: **516 passed, 81 skipped, 2 warnings**;
- F7 focused tests: **5/5 PASS**;
- frontend focused: **30/30 PASS**;
- lint: **0 warnings / 0 errors**;
- TypeScript type-check: PASS;
- production build: PASS;
- migrations through `0038_durable_assistant_runs`: PASS;
- application startup, health and runtime checks: PASS;
- runtime readiness: **7 checks PASS**;
- cleanup: PASS, 1 smoke session archived;
- `smoke-real`: **SKIPPED** and is not PASS evidence.

The five F7 regressions prove:

1. restricted/denied descriptors are removed before the rank function sees them;
2. invalid and foreign artifacts do not enter broker context/catalog and raw paths are not exposed;
3. restricted Memory Hub records do not enter catalog/context;
4. the provider receives only broker-authorized context;
5. the context manifest does not expose denied unvalidated artifact IDs, raw paths, or denied content in `included`/`retrieved`.

## Known non-blocking semantics

- `context-manifest.accessible` is a browser provenance compatibility group and is not consumed by the model/ranker/provider. It may be broader than the broker's hydrated text-resource set; clients must not infer model use from accessibility. `retrieved`, `used` and `targeted` retain their distinct provenance meanings.
- Conversation history is durable app-owned history, but GYO/provider-authored portions remain untrusted content even when the resource descriptor identifies the app-owned transcript source.
- Existing dependency/tool-version warnings, npm audit findings, branch protection, admin human-presence hardening, migration-wrapper debt and sandbox TOCTOU are separate gates and are not changed by F7.

## Gate effect

F7 Resource Catalog + Context Broker is implemented and has scoped exact-head CI evidence. This does not promote the overall project checkpoint.

State remains:

`DIRAP_V22_IMPLEMENTATION_IN_PROGRESS / PARTIAL`

F9 Data Egress remains **CLOSED / NOT APPROVED**.
