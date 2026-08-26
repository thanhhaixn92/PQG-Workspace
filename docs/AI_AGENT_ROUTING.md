# AI agent routing

Use this index after the mandatory preflight. Read the smallest relevant set;
never load every project document by default.

## Always read before code

1. `AGENTS.md`
2. `PROJECT_STATE.md` and `AI_STATE.json`
3. `docs/implementation/CURRENT_CHECKPOINT.md`
4. `CODEGRAPH.md`
5. `docs/14_AGENT_OPERATING_CONTRACT.md`

The active state files define the gate. Historical plans, historical test counts
and older checkpoint wording do not authorize a change.

## Active coding-operations route

For coding-operations state, checkpoint, evidence, or handoff work, read the
current [Issue #13](https://github.com/thanhhaixn92/PQG-Workspace/issues/13),
the active state triplet, root `AGENTS.md`, and the operating contract. Issue
#13 is the active coordination plan; exact dynamic SHA/run evidence remains in
GitHub. CP6, Outbox, Antigravity, Hermes/ACP launcher flows, PR #9, and old MVP
plans are historical or compatibility inputs, not active routing.

## Task routing

| Task | Read first | Inspect next | Prove with |
| --- | --- | --- | --- |
| Work, plan or conversation | data model, security policy | `api/works.py`, schemas, `WorkHub.tsx` | Work/scope/archive tests |
| GYO chat, stream, retry or cancel | PRD, security policy | `api/assistant.py`, orchestrator, SSE client/panel | assistant route + UI isolation tests |
| Provider/model/fallback | `docs/implementation/PQG_GYO_PROVIDER_CORE.md`, security | model-config, registry, resilience service | provider/secret/fallback tests |
| F7 Resource Catalog / Context Broker | `docs/implementation/F7_RESOURCE_CATALOG_CONTEXT_BROKER.md`, data model, security policy | `services/context_broker.py`, compatibility context builder, assistant manifest/provider boundary | security-filter-before-rank, foreign/restricted/path-redaction/provider-context tests |
| Attachment/context/memory scope | data model, security policy | Context Broker, scope service, manifest/panel | foreign scope/exclusion/retry tests |
| Learning candidate/worker | security policy, current checkpoint | learning API/service/worker | default-off, duplicate, cancel/archive tests |
| Action Package or approval | security policy, data model | proposal parser, package/approval routes, UI entry point | before-approval, 409, idempotency tests |
| Files/artifacts/reports | data model, security policy | file/artifact routes, sandbox, explorer/reports | managed-root/path-escape tests |
| Knowledge, Skill, Memory review | PRD, security policy | source lifecycle route + Review Inbox | lifecycle/concurrency/deep-link tests |
| App shell or responsive UI | `DESIGN.md` plus state | AppLayout, target component, CSS, focused test | loading/error/keyboard/reflow browser evidence |
| State/checkpoint/evidence | Issue #13, active state triplet, `AGENTS.md`, operating contract | exact GitHub evidence plus affected governance files | state consistency, exact commands/artifacts, scoped diff |
| Migration/dependency/config | data model, security policy | migration/config/package manifest | explicit approval then isolated upgrade/rollback |
| GitHub/GitLab/Codex CI, mirror or connector | `docs/15_GITHUB_GITLAB_CODEX_WORKFLOW.md`, security policy | `.gitlab-ci.yml`, GitHub workflows, live protection/mirror settings | exact SHA equality, CI Lint, exact pipeline receipt, secret-safe diff |

## Routing guardrails

- F7 Context Broker changes must preserve the hard ordering `discover metadata → SECURITY FILTER → relevance/ranking → hydrate → pack`. A ranker, model or model-facing selector must never receive a resource descriptor that failed authorization. Denied resource IDs, titles, backend locators and content remain outside model-visible catalog/context.
- F7 does not authorize F9 Data Egress. Local read authorization is not permission to send data to a provider other than the already-approved local GYO provider boundary, web search, connectors, upload/export or any other external destination.
- When `DESIGN.md` or a historical Hermes document conflicts with current GYO
  route/service code, do not reintroduce old runtime behaviour. Record the
  discrepancy and request a documentation-reconciliation scope.
- A UI selector, model prompt, or frontend condition is not an authorization or
  scope control. Verify the backend route/service guard.
- For a UI change, inspect the affected async, empty and error states before
  changing layout. Do not use visual similarity as proof of workflow safety.
- For shared contract changes, read both producer and consumer tests before the
  first edit.
- Preserve the dirty worktree. Use a focused diff before and after the change.

## Verification order

1. Focused regression tests.
2. Type check/build only when shared client/component contracts change.
3. Runtime/browser proof only when a route, streaming, layout or gate is
   affected.
4. `git diff --check` and scoped diff review.

Mark every skipped or unrun check explicitly. A successful focused check is not
a release gate and does not promote the current checkpoint.
