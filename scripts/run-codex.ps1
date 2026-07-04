$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Read-AIState {
    Get-Content -Raw -LiteralPath "AI_STATE.json" | ConvertFrom-Json
}

function Write-AIState($State) {
    $State | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath "AI_STATE.json" -Encoding UTF8
}

$state = Read-AIState

if ($state.state -eq "CP5_COMPLETE" -and $state.next_agent -eq "human") {
    Write-Host "Stopped: CP5_COMPLETE is waiting for human approval."
    exit 0
}
if ($state.state -eq "BLOCKED" -or $state.human_approval_required -eq $true -or $null -ne $state.lock) {
    Write-Host "Stopped: state gate is closed. state=$($state.state) next_agent=$($state.next_agent) lock=$($state.lock) human_approval_required=$($state.human_approval_required)"
    exit 0
}
if ($state.next_agent -ne "codex") {
    Write-Host "Stopped: next_agent is $($state.next_agent), not codex."
    exit 0
}

$state.lock = "codex"
Write-AIState $state

try {
    $prompt = @"
Read AGENTS.md, AI_TASK.md, AI_STATE.json, AI_HANDOFF.md, AI_CHANGELOG.md, AI_VERIFICATION.md, and AI_RISK_REGISTER.md.
Follow only AI_HANDOFF.md.
Never commit, push, merge, deploy, reset, clean, delete, or modify forbidden files.
Only work on CP6 when AI_STATE.json and AI_HANDOFF.md explicitly show CP6 is approved, human_approval_required is false, and next_agent is codex.
For the current approved CP6 task, implement only the Outbox Dispatcher scope described in AI_TASK.md and AI_HANDOFF.md.
"@
    codex exec --sandbox workspace-write $prompt
}
finally {
    $current = Read-AIState
    if ($current.lock -eq "codex") {
        $current.lock = $null
        Write-AIState $current
    }
}
