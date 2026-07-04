$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Show-ToolVersion($Name, $Arguments) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        Write-Host "$Name unavailable"
        return
    }
    try {
        & $command.Source @Arguments 2>&1
    }
    catch {
        Write-Host "$Name version check failed: $($_.Exception.Message)"
    }
}

Write-Host "AI automation environment summary"
Write-Host "PWD: $Root"

Show-ToolVersion "python" @("--version")
Show-ToolVersion "node" @("--version")
Show-ToolVersion "npm" @("--version")
Show-ToolVersion "bash" @("--version")
Show-ToolVersion "codex" @("--version")
Show-ToolVersion "antigravity" @("--version")
Show-ToolVersion "ag" @("--version")

& (Join-Path $PSScriptRoot "agent-loop.ps1")

Write-Host "Final git status:"
git status --short
Write-Host "Review git diff manually. This script never commits automatically."
