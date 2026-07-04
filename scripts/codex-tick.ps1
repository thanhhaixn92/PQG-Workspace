$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$state = Get-Content -Raw -LiteralPath "AI_STATE.json" | ConvertFrom-Json

if ($state.next_agent -ne "codex" -or $null -ne $state.lock -or $state.human_approval_required -eq $true) {
    Write-Host "Stopped: codex tick gate is closed. state=$($state.state) next_agent=$($state.next_agent) lock=$($state.lock) human_approval_required=$($state.human_approval_required)"
    exit 0
}

& (Join-Path $PSScriptRoot "run-codex.ps1")
