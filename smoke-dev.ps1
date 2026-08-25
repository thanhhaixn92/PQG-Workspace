param(
    [int]$BackendPort = 0,
    [string]$WorkspacePath = "",
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StatePath = Join-Path $Root ".dev\dev-state.json"

if ((Test-Path $StatePath) -and $BackendPort -eq 0) {
    $state = Get-Content $StatePath -Raw | ConvertFrom-Json
    $BackendPort = [int]$state.backendPort
}

if ($BackendPort -eq 0) {
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

$PreviousLocation = Get-Location
try {
    Set-Location (Join-Path $Root "backend")
    Write-Host "RUN native GYO integrated journey (offline/provider-independent)"
    & $PythonCommand -m pytest tests/test_uat_p0_local_pilot.py -q
    Assert-Ok ($LASTEXITCODE -eq 0) "Native GYO integrated journey failed"
} finally {
    Set-Location $PreviousLocation
}

Write-Host "OK  native GYO integrated journey completed"
Write-Host "OK  smoke test completed"
