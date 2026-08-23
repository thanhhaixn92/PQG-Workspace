param(
    [string]$BackendUrl = "http://127.0.0.1:8000",
    [string]$FrontendOrigin = "http://localhost:5173"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $Root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Missing backend\.venv. Run start-dev.ps1 after preparing the environment."
}

try {
    $health = Invoke-RestMethod -Uri "$BackendUrl/health" -TimeoutSec 5
    if ($health.status -ne "ok") { throw "Backend is not ready." }
    Write-Host "OK  Backend and SQLite are ready." -ForegroundColor Green
} catch {
    throw "Cannot connect to backend at $BackendUrl. Run .\start-dev.ps1 -NoReload first."
}

$credentialCheck = @'
import keyring
service = "dirap-memory-hub"
roles = ("hermes", "opencode", "antigravity", "codex", "user")
missing = [role for role in roles if not keyring.get_password(service, role)]
if missing:
    print("MISSING:" + ",".join(missing))
else:
    print("READY")
'@ | & $PythonExe -

if ($LASTEXITCODE -ne 0) {
    throw "Cannot check Windows Credential Manager."
}
if ($credentialCheck -match "^MISSING:(.+)$") {
    Write-Host "WARN Missing Memory Hub credentials for role: $($Matches[1]). See docs\implementation\MEMORY_HUB_CREDENTIAL_BOOTSTRAP.md." -ForegroundColor Yellow
} else {
    Write-Host "OK  Memory Hub credentials are present for configured roles." -ForegroundColor Green
}

try {
    Invoke-RestMethod -Uri "$BackendUrl/api/memory-hub/operator/records?include_global_preferences=true" -Headers @{ Origin = $FrontendOrigin } -TimeoutSec 5 | Out-Null
    Write-Host "OK  Local Memory Hub UI can call the operator boundary." -ForegroundColor Green
} catch {
    throw "Memory Hub UI cannot reach the operator boundary. Check CORS_ORIGINS matches $FrontendOrigin and restart start-dev.ps1."
}

Write-Host "Memory Hub is ready: open the frontend, select Memory Hub, then choose an explicit scope." -ForegroundColor Green
