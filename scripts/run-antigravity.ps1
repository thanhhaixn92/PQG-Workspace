$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Read-AIState {
    Get-Content -Raw -LiteralPath "AI_STATE.json" | ConvertFrom-Json
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

if ($antigravity) {
    Write-Host "Antigravity CLI detected. Safe prompt:"
    Write-Host $prompt
    & $antigravity.Source $prompt
}
elseif ($ag) {
    Write-Host "ag CLI detected. Safe prompt:"
    Write-Host $prompt
    & $ag.Source $prompt
}
else {
    Write-Host "Antigravity CLI not found."
    Write-Host "GUI fallback:"
    Write-Host "1. Open Antigravity IDE."
    Write-Host "2. Open this repo: $Root"
    Write-Host "3. Run /verify-and-handoff."
}
