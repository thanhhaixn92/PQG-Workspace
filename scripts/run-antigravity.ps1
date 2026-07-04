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

function Get-CommandOrKnownPath($Name, $KnownPath) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command
    }
    if ($KnownPath -and (Test-Path -LiteralPath $KnownPath)) {
        return [pscustomobject]@{
            Name = $Name
            Source = $KnownPath
        }
    }
    return $null
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
$agy = Get-CommandOrKnownPath "agy" (Join-Path $env:LOCALAPPDATA "agy\bin\agy.exe")
$antigravity = Get-Command antigravity -ErrorAction SilentlyContinue
$ag = Get-Command ag -ErrorAction SilentlyContinue

function Get-UsableAntigravityCli {
    param($Candidates)

    foreach ($candidate in $Candidates) {
        if ($null -eq $candidate) {
            continue
        }
        $helpText = ""
        try {
            $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
            $startInfo.FileName = $candidate.Source
            $startInfo.Arguments = "--help"
            $startInfo.RedirectStandardOutput = $true
            $startInfo.RedirectStandardError = $true
            $startInfo.UseShellExecute = $false
            $process = [System.Diagnostics.Process]::Start($startInfo)
            $stdout = $process.StandardOutput.ReadToEnd()
            $stderr = $process.StandardError.ReadToEnd()
            $process.WaitForExit()
            $helpText = "$stdout`n$stderr"
            if ($process.ExitCode -ne 0 -and [string]::IsNullOrWhiteSpace($helpText)) {
                Write-Host "Skipping $($candidate.Name): --help failed with exit code $($process.ExitCode)."
                continue
            }
        }
        catch {
            Write-Host "Skipping $($candidate.Name): --help failed: $($_.Exception.Message)"
            continue
        }
        if ($helpText -match "(^|\s)-p(\s|,|$)" -or $helpText -match "--prompt") {
            return [pscustomobject]@{
                Name = $candidate.Name
                Source = $candidate.Source
                UseSandbox = ($helpText -match "--sandbox")
            }
        }
        Write-Host "Skipping $($candidate.Name): non-interactive -p/--prompt support was not found in --help."
    }

    return $null
}

$cli = Get-UsableAntigravityCli @($agy, $antigravity, $ag)

if ($null -eq $cli) {
    Write-Host "Antigravity CLI not found."
    Write-Host "GUI fallback:"
    Write-Host "1. Open Antigravity IDE."
    Write-Host "2. Open this repo: $Root"
    Write-Host "3. Run /verify-and-handoff."
    Block-Antigravity "Antigravity CLI unavailable or missing non-interactive -p support. Human must use GUI fallback and explicitly reset AI_STATE.json before resuming automation."
    exit 0
}

$state.lock = "antigravity"
Write-AIState $state

try {
    Write-Host "$($cli.Name) CLI detected. Safe prompt:"
    Write-Host $prompt
    if ($cli.UseSandbox) {
        & $cli.Source --sandbox -p $prompt
    }
    else {
        & $cli.Source -p $prompt
    }
    if ($LASTEXITCODE -ne 0) {
        Block-Antigravity "$($cli.Name) CLI execution failed with exit code $LASTEXITCODE."
        exit $LASTEXITCODE
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
