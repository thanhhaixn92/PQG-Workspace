param(
    [int]$BackendPort = 0,
    [string]$WorkspacePath = "",
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StatePath = Join-Path $Root ".dev\dev-state.json"
$BackendPortWasExplicit = $PSBoundParameters.ContainsKey('BackendPort')

if ($BackendPortWasExplicit) {
    if ($BackendPort -le 0 -or $BackendPort -gt 65535) { throw 'BackendPort must be between 1 and 65535.' }
} elseif (Test-Path -LiteralPath $StatePath -PathType Leaf) {
    try { $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json }
    catch { throw "Dev-state exists but is not valid JSON: $StatePath" }
    if ($null -eq $state.PSObject.Properties['schemaVersion'] -or [int]$state.schemaVersion -ne 2) {
        throw "Dev-state schemaVersion must be 2: $StatePath"
    }
    if ($null -eq $state.backend -or $null -eq $state.backend.PSObject.Properties['port']) {
        throw "Dev-state backend.port is required: $StatePath"
    }
    $recordedBackendPort = 0
    if (-not [int]::TryParse([string]$state.backend.port, [ref]$recordedBackendPort) -or $recordedBackendPort -le 0 -or $recordedBackendPort -gt 65535) {
        throw "Dev-state backend.port must be between 1 and 65535: $StatePath"
    }
    $BackendPort = $recordedBackendPort
} else {
    $BackendPort = 8000
}

if (-not $WorkspacePath) {
    $WorkspacePath = $Root
}

$BackendUrl = "http://127.0.0.1:$BackendPort"

function Assert-Ok {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

Write-Host "Smoke test PQG Workspace" -ForegroundColor Cyan
Write-Host "Backend: $BackendUrl"
Write-Host "Runtime workspace: $WorkspacePath"
Write-Host "Native GYO acceptance uses its own temporary SQLite DB/workspace and no provider network."

$health = Invoke-RestMethod "$BackendUrl/health" -TimeoutSec 10
Assert-Ok ($health.status -eq "ok") "Backend health failed"
Write-Host "OK  health"

$runtime = Invoke-RestMethod "$BackendUrl/api/runtime/status" -TimeoutSec 10
Assert-Ok ($runtime.backend -eq "ok") "Runtime status failed"
Assert-Ok ($runtime.db.status -eq "ok") "DB status failed"
Write-Host "OK  runtime backend + DB readiness"

# The product acceptance journey is the deterministic current durable GYO test,
# not the historical /api/sessions/{id}/prompt + Hermes event stream. Running
# it here keeps local smoke provider-independent and avoids writing to the live
# runtime database/workspace while still exercising the real FastAPI/GYO path.
$VenvPython = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonCommand = $VenvPython
} else {
    $Python = Get-Command python -ErrorAction SilentlyContinue
    Assert-Ok ($null -ne $Python) "Python is required to run the native GYO acceptance journey"
    $PythonCommand = $Python.Source
}
Assert-Ok ($TimeoutSeconds -gt 0) "TimeoutSeconds must be greater than zero"

$PreviousLocation = Get-Location
try {
    Set-Location (Join-Path $Root "backend")
    Write-Host "RUN native GYO integrated journey (offline/provider-independent)"
    $pytest = Start-Process `
        -FilePath $PythonCommand `
        -ArgumentList @("-m", "pytest", "tests/test_uat_p0_local_pilot.py", "-q") `
        -NoNewWindow `
        -PassThru
    $timeoutMilliseconds = [int][Math]::Min(([double]$TimeoutSeconds * 1000), [int]::MaxValue)
    if (-not $pytest.WaitForExit($timeoutMilliseconds)) {
        Stop-Process -Id $pytest.Id -Force -ErrorAction SilentlyContinue
        $pytest.WaitForExit()
        throw "Native GYO integrated journey timed out after $TimeoutSeconds seconds"
    }
    Assert-Ok ($pytest.ExitCode -eq 0) "Native GYO integrated journey failed"
} finally {
    Set-Location $PreviousLocation
}

Write-Host "OK  native GYO integrated journey completed"
Write-Host "OK  smoke test completed"
