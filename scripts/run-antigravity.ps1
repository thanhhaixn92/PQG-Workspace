$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Read-AIState {
    Get-Content -Raw -LiteralPath "AI_STATE.json" | ConvertFrom-Json
}

function Write-AIState($State) {
    $State | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath "AI_STATE.json" -Encoding UTF8
}

function Block-Antigravity($Message) {
    $blocked = Read-AIState
    $blocked.state = "BLOCKED"
    $blocked.next_agent = "human"
    $blocked.lock = $null
    $blocked.last_agent = "automation"
    $blocked.last_result = $Message
    $blocked.human_approval_required = $true
    $blocked.risk_level = "medium"
    Write-AIState $blocked
    Write-Host "Blocked: $Message"
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
if ($state.next_agent -ne "antigravity") {
    Write-Host "Stopped: next_agent is $($state.next_agent), not antigravity."
    exit 0
}

$prompt = "Read .agents/skills/verify-and-handoff/SKILL.md and run /verify-and-handoff with safe checks only."
$antigravity = Get-Command antigravity -ErrorAction SilentlyContinue
$ag = Get-Command ag -ErrorAction SilentlyContinue

if ($null -eq $antigravity -and $null -eq $ag) {
    Write-Host "Antigravity CLI not found."
    Write-Host "GUI fallback:"
    Write-Host "1. Open Antigravity IDE."
    Write-Host "2. Open this repo: $Root"
    Write-Host "3. Run /verify-and-handoff."
    Block-Antigravity "Antigravity CLI unavailable. Human must use GUI fallback and explicitly reset AI_STATE.json before resuming automation."
    exit 0
}

$state.lock = "antigravity"
Write-AIState $state

try {
    if ($antigravity) {
        Write-Host "Antigravity CLI detected. Safe prompt:"
        Write-Host $prompt
        & $antigravity.Source $prompt
        if ($LASTEXITCODE -ne 0) {
            Block-Antigravity "Antigravity CLI execution failed with exit code $LASTEXITCODE."
            exit $LASTEXITCODE
        }
    }
    else {
        Write-Host "ag CLI detected. Safe prompt:"
        Write-Host $prompt
        & $ag.Source $prompt
        if ($LASTEXITCODE -ne 0) {
            Block-Antigravity "ag CLI execution failed with exit code $LASTEXITCODE."
            exit $LASTEXITCODE
        }
    }
}
catch {
    Block-Antigravity "Antigravity CLI execution failed: $($_.Exception.Message)"
    throw
}
finally {
    $current = Read-AIState
    if ($current.lock -eq "antigravity") {
        $current.lock = $null
        Write-AIState $current
    }
}
