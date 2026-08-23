[CmdletBinding()]
param(
    [switch]$Launch,
    [string]$TaskPrompt
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& (Join-Path $PSScriptRoot "agent-preflight.ps1")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$State = Get-Content -LiteralPath "AI_STATE.json" -Raw -Encoding UTF8 | ConvertFrom-Json
if ($State.human_approval_required -eq $true) {
    Write-Host "Stopped: the current state requires human approval before an implementation task can launch."
    exit 3
}

if (-not $Launch) {
    Write-Host "Preflight complete. Review the required files, then re-run with -Launch -TaskPrompt '<approved scope>' only for an approved scoped task."
    exit 0
}

if ([string]::IsNullOrWhiteSpace($TaskPrompt)) {
    Write-Host "Stopped: -TaskPrompt is required when -Launch is used."
    exit 4
}

$Prompt = @"
Before any edit, read AGENTS.md and run scripts/agent-preflight.ps1.
Read PROJECT_STATE.md, AI_STATE.json, docs/implementation/CURRENT_CHECKPOINT.md,
CODEGRAPH.md, docs/AI_AGENT_ROUTING.md and docs/14_AGENT_OPERATING_CONTRACT.md.
State the active gate, requested scope, files inspected and focused validation
before editing. Preserve the dirty worktree. Never commit, push, deploy, reset,
clean, alter credentials, database files, migrations, or state/checkpoints
without explicit human approval. Do not treat historical plans or tests as the
current implementation scope.

Approved task scope:
$TaskPrompt
"@

codex exec --sandbox workspace-write $Prompt
