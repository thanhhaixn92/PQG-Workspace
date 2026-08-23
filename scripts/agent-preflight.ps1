[CmdletBinding()]
param(
    [switch]$AsJson
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$RequiredFiles = @(
    "AGENTS.md",
    "CODEGRAPH.md",
    "PROJECT_STATE.md",
    "AI_STATE.json",
    "docs/implementation/CURRENT_CHECKPOINT.md",
    "docs/AI_AGENT_ROUTING.md",
    "docs/14_AGENT_OPERATING_CONTRACT.md"
)

$MissingFiles = @($RequiredFiles | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
$State = $null
$StateError = $null
try {
    $State = Get-Content -LiteralPath "AI_STATE.json" -Raw -Encoding UTF8 | ConvertFrom-Json
}
catch {
    $StateError = $_.Exception.Message
}

$GitStatus = @(cmd.exe /d /c "git -c core.safecrlf=false status --short 2>&1")
$ModifiedCount = @($GitStatus | Where-Object { $_ -match '^[ MARCUD][MARCDU] ' }).Count
$UntrackedCount = @($GitStatus | Where-Object { $_ -match '^\?\? ' }).Count
$DiffCheck = @(cmd.exe /d /c "git -c core.safecrlf=false diff --check 2>&1")
$DiffCheckExitCode = $LASTEXITCODE

$Result = [ordered]@{
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    repository = $Root
    required_context = [ordered]@{
        files = $RequiredFiles
        missing = $MissingFiles
    }
    active_state = [ordered]@{
        state = if ($State) { $State.state } else { $null }
        human_approval_required = if ($State) { [bool]$State.human_approval_required } else { $null }
        parse_error = $StateError
    }
    worktree = [ordered]@{
        modified_entries = $ModifiedCount
        untracked_entries = $UntrackedCount
        diff_check_exit_code = $DiffCheckExitCode
        diff_check_output = $DiffCheck
    }
    read_before_edit = @(
        "PROJECT_STATE.md",
        "AI_STATE.json",
        "docs/implementation/CURRENT_CHECKPOINT.md",
        "CODEGRAPH.md",
        "docs/AI_AGENT_ROUTING.md",
        "docs/14_AGENT_OPERATING_CONTRACT.md",
        "target source, public contract and focused tests"
    )
    instructions = @(
        "This script is read-only and does not grant permission to edit.",
        "Preserve existing dirty changes; inspect a focused diff before editing.",
        "A true human_approval_required value blocks unapproved feature/state changes.",
        "Report any missing context, malformed state, or diff-check failure before editing."
    )
}

if ($AsJson) {
    $Result | ConvertTo-Json -Depth 6
}
else {
    Write-Host "PQG Workspace agent preflight (read-only)"
    Write-Host "Repository: $Root"
    Write-Host "Active state: $($Result.active_state.state)"
    Write-Host "Human approval required: $($Result.active_state.human_approval_required)"
    Write-Host "Dirty entries: modified=$ModifiedCount; untracked=$UntrackedCount"
    Write-Host "diff --check exit: $DiffCheckExitCode"
    if ($MissingFiles.Count -gt 0) { Write-Host "Missing required context: $($MissingFiles -join ', ')" }
    if ($StateError) { Write-Host "AI_STATE parse error: $StateError" }
    if ($DiffCheck.Count -gt 0) { Write-Host "diff --check output:"; $DiffCheck | ForEach-Object { Write-Host $_ } }
    Write-Host "Read before edit:"
    $Result.read_before_edit | ForEach-Object { Write-Host " - $_" }
    Write-Host "This report is not permission to change protected files or promote a gate."
}

if ($MissingFiles.Count -gt 0 -or $StateError) {
    exit 2
}
