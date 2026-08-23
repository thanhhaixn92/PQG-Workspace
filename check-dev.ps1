param(
    [int]$BackendPort = 0,
    [int]$FrontendPort = 0
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StatePath = Join-Path $Root ".dev\dev-state.json"
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
$BackendEnv = Join-Path $BackendDir ".env"

function Test-HttpOk {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    } catch {
        return $false
    }
}

if ((Test-Path $StatePath) -and ($BackendPort -eq 0 -or $FrontendPort -eq 0)) {
    $state = Get-Content $StatePath -Raw | ConvertFrom-Json
    if ($BackendPort -eq 0) { $BackendPort = [int]$state.backendPort }
    if ($FrontendPort -eq 0) { $FrontendPort = [int]$state.frontendPort }
}

if ($BackendPort -eq 0) { $BackendPort = 8000 }
if ($FrontendPort -eq 0) { $FrontendPort = 5173 }

Write-Host "Kiem tra DIRAP Local Workbench" -ForegroundColor Cyan

if (Test-Path $PythonExe) {
    Write-Host "OK  backend\.venv ton tai" -ForegroundColor Green
} else {
    Write-Host "ERR thieu backend\.venv" -ForegroundColor Red
}

if (Test-Path (Join-Path $FrontendDir "node_modules")) {
    Write-Host "OK  frontend\node_modules ton tai" -ForegroundColor Green
} else {
    Write-Host "ERR thieu frontend\node_modules" -ForegroundColor Red
}

if (Test-Path $BackendEnv) {
    Write-Host "OK  backend\.env ton tai" -ForegroundColor Green
    $envText = Get-Content $BackendEnv -Raw
    if ($envText -match "(?m)^\s*HERMES_DEV_MOCK\s*=\s*(1|true|True|TRUE)\s*$") {
        Write-Host "OK  Hermes dev mock dang bat" -ForegroundColor Green
    } elseif ($envText -match "(?m)^\s*HERMES_EXECUTABLE_PATH\s*=\s*(.+?)\s*$") {
        Write-Host "OK  HERMES_EXECUTABLE_PATH da cau hinh" -ForegroundColor Green
    } else {
        Write-Host "WARN chua thay HERMES_EXECUTABLE_PATH; bat HERMES_DEV_MOCK=1 neu muon chat thu" -ForegroundColor Yellow
    }
} else {
    Write-Host "WARN chua co backend\.env; tao bang: Copy-Item backend\.env.example backend\.env" -ForegroundColor Yellow
}

$backendUrl = "http://127.0.0.1:$BackendPort"
$frontendUrl = "http://localhost:$FrontendPort"

if (Test-HttpOk "$backendUrl/health") {
    Write-Host "OK  backend phan hoi: $backendUrl" -ForegroundColor Green
    try {
        $runtime = Invoke-RestMethod "$backendUrl/api/runtime/status" -TimeoutSec 5
        Write-Host "OK  DB: $($runtime.db.status)" -ForegroundColor Green
        Write-Host "OK  Hermes status: $($runtime.hermes.status)" -ForegroundColor Green
        if ($runtime.hermes.status -eq "mock") {
            Write-Host "OK  Hermes mock mode is enabled" -ForegroundColor Green
        } elseif ($runtime.hermes.status -eq "ready") {
            Write-Host "OK  Hermes executable is ready" -ForegroundColor Green
        } else {
            Write-Host "WARN Hermes needs configuration; open the app system panel for details" -ForegroundColor Yellow
        }
        Write-Host "OK  n8n configured: $($runtime.n8n.configured)" -ForegroundColor Green
    } catch {
        Write-Host "WARN backend chay nhung runtime status khong doc duoc" -ForegroundColor Yellow
    }
} else {
    Write-Host "ERR backend chua phan hoi tai $backendUrl" -ForegroundColor Red
}

if (Test-HttpOk $frontendUrl) {
    Write-Host "OK  frontend phan hoi: $frontendUrl" -ForegroundColor Green
} else {
    Write-Host "ERR frontend chua phan hoi tai $frontendUrl" -ForegroundColor Red
}

Write-Host ""
Write-Host "Mo app: $frontendUrl"
