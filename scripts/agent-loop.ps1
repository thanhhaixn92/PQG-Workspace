$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Read-AIState {
    Get-Content -Raw -LiteralPath "AI_STATE.json" | ConvertFrom-Json
}

while ($true) {
    $state = Read-AIState

    if ($state.state -eq "BLOCKED" -or $state.human_approval_required -eq $true -or $null -ne $state.lock) {
        Write-Host "Stopped: state gate is closed. state=$($state.state) next_agent=$($state.next_agent) lock=$($state.lock) human_approval_required=$($state.human_approval_required)"
        exit 0
    }
    if ($state.state -eq "CP5_COMPLETE" -and $state.next_agent -eq "human") {
        Write-Host "Stopped: CP5_COMPLETE is waiting for human approval."
        exit 0
    }

    $before = $state | ConvertTo-Json -Depth 10

    switch ($state.next_agent) {
        "codex" { & (Join-Path $PSScriptRoot "run-codex.ps1") }
        "antigravity" { & (Join-Path $PSScriptRoot "run-antigravity.ps1") }
        "human" {
            Write-Host "Stopped: next_agent is human."
            exit 0
        }
        "done" {
            Write-Host "Stopped: next_agent is done."
            exit 0
        }
        default {
            Write-Host "Stopped: unknown next_agent $($state.next_agent)."
            exit 1
        }
    }

    $afterState = Read-AIState
    $after = $afterState | ConvertTo-Json -Depth 10
    if ($after -eq $before) {
        Write-Host "Stopped: agent run made no state change. Manual review required to avoid an infinite loop."
        exit 0
    }
}
