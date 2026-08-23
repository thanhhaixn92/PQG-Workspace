# Personal Memory Hub — credential bootstrap

Gói 3 reads role-scoped bearer tokens only from the operating system credential
manager through `keyring`. Tokens must never be placed in source, `.env`, the
SQLite database, logs, or MCP arguments.

Before a real REST or MCP run, an authorized operator must create one distinct
token for each approved role (`hermes`, `opencode`, `antigravity`, `codex`, or
`user`) in the Windows Credential Manager service:

`dirap-memory-hub`

The account name is the role and the credential value is its bearer token.
The MCP process uses `MEMORY_HUB_MCP_ROLE` to select its own role; it cannot
choose a role from a tool call. The API endpoint is constrained to loopback by
`MEMORY_HUB_API_BASE_URL` (default `http://127.0.0.1:8000`).

Credential creation is an operator-controlled action. Existing role credentials
must be distinct; the API fails closed if one token matches more than one role.
Rotate or remove a role token in Credential Manager if access changes, then
restart the relevant local process.
