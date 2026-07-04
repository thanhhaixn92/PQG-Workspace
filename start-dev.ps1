param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$Fresh,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$DevDir = Join-Path $Root ".dev"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
$BackendEnv = Join-Path $BackendDir ".env"

function Test-PortAvailable {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return -not $connection
}

function Test-HttpOk {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    } catch {
        return $false
    }
}

function Find-AvailablePort {
    param(
        [int]$StartPort,
        [int]$MaxAttempts = 20
    )

    for ($offset = 0; $offset -lt $MaxAttempts; $offset++) {
        $candidate = $StartPort + $offset
        if (Test-PortAvailable $candidate) {
            return $candidate
        }
    }

    throw "Khong tim thay cong trong tu $StartPort den $($StartPort + $MaxAttempts - 1)."
}

function Write-DevState {
    param(
        [int]$BackendPort,
        [int]$FrontendPort,
        [int]$BackendPid,
        [int]$FrontendPid
    )

    if (-not (Test-Path $DevDir)) {
        New-Item -ItemType Directory -Path $DevDir | Out-Null
    }

    @"
{
  "backendPort": $BackendPort,
  "frontendPort": $FrontendPort,
  "backendPid": $BackendPid,
  "frontendPid": $FrontendPid,
  "startedAt": "$(Get-Date -Format o)"
}
"@ | Set-Content -Path (Join-Path $DevDir "dev-state.json") -Encoding UTF8
}

Write-Host "Khoi dong moi truong phat trien Hermes Local Stack" -ForegroundColor Cyan

if (-not (Test-Path $PythonExe)) {
    Write-Host "Chua co moi truong Python: backend\.venv" -ForegroundColor Yellow
    Write-Host "Tao bang lenh: cd backend; py -3.11 -m venv .venv; .venv\Scripts\pip.exe install -e `".[dev]`""
    exit 1
}

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "Chua cai dependency frontend: frontend\node_modules" -ForegroundColor Yellow
    Write-Host "Cai bang lenh: cd frontend; npm install"
    exit 1
}

if (-not (Test-Path $BackendEnv)) {
    Write-Host "Chua co backend\.env" -ForegroundColor Yellow
    Write-Host "Tao tu template bang lenh: Copy-Item backend\.env.example backend\.env"
    Write-Host "Muon chat thu ngay: dat HERMES_DEV_MOCK=1 trong backend\.env"
} else {
    $envText = Get-Content $BackendEnv -Raw
    $mockEnabled = $envText -match "(?m)^\s*HERMES_DEV_MOCK\s*=\s*(1|true|True|TRUE)\s*$"
    $hasHermesPath = $envText -match "(?m)^\s*HERMES_EXECUTABLE_PATH\s*=\s*(.+?)\s*$"
    if ($mockEnabled) {
        Write-Host "Hermes dev mock dang bat. Ban co the chat thu end-to-end." -ForegroundColor Green
    } elseif (-not $hasHermesPath) {
        Write-Host "Chua thay HERMES_EXECUTABLE_PATH trong backend\.env." -ForegroundColor Yellow
        Write-Host "Neu chua cai Hermes, dat HERMES_DEV_MOCK=1 de chat thu bang mock."
    }
}

$BackendAlreadyRunning = $false
$FrontendAlreadyRunning = $false
$BackendPid = 0
$FrontendPid = 0

if (-not (Test-PortAvailable $BackendPort)) {
    if ($Fresh) {
        $oldPort = $BackendPort
        $BackendPort = Find-AvailablePort ($BackendPort + 1)
        Write-Host "Cong backend $oldPort dang ban. Dung cong moi: $BackendPort" -ForegroundColor Yellow
    } elseif (Test-HttpOk "http://127.0.0.1:$BackendPort/health") {
        $BackendAlreadyRunning = $true
        Write-Host "Backend da dang chay tai http://127.0.0.1:$BackendPort" -ForegroundColor Green
    } else {
        $oldPort = $BackendPort
        $BackendPort = Find-AvailablePort ($BackendPort + 1)
        Write-Host "Cong backend $oldPort dang duoc su dung boi tien trinh khac. Dung cong moi: $BackendPort" -ForegroundColor Yellow
    }
}

if (-not (Test-PortAvailable $FrontendPort)) {
    if ($Fresh) {
        $oldPort = $FrontendPort
        $FrontendPort = Find-AvailablePort ($FrontendPort + 1)
        Write-Host "Cong frontend $oldPort dang ban. Dung cong moi: $FrontendPort" -ForegroundColor Yellow
    } elseif (Test-HttpOk "http://localhost:$FrontendPort") {
        $FrontendAlreadyRunning = $true
        Write-Host "Frontend da dang chay tai http://localhost:$FrontendPort" -ForegroundColor Green
    } else {
        $oldPort = $FrontendPort
        $FrontendPort = Find-AvailablePort ($FrontendPort + 1)
        Write-Host "Cong frontend $oldPort dang duoc su dung boi tien trinh khac. Dung cong moi: $FrontendPort" -ForegroundColor Yellow
    }
}

if (-not $BackendAlreadyRunning) {
    Write-Host "Dang chay backend tai http://127.0.0.1:$BackendPort"
    $reloadFlag = if ($NoReload) { "" } else { " --reload" }
    $backendCommand = "`$env:CORS_ORIGINS='http://localhost:$FrontendPort'; .\.venv\Scripts\python.exe -m uvicorn app.main:app$reloadFlag --host 127.0.0.1 --port $BackendPort"
    $backendProcess = Start-Process powershell -WindowStyle Hidden -WorkingDirectory $BackendDir -PassThru -ArgumentList @(
        "-NoExit",
        "-Command",
        $backendCommand
    )
    $BackendPid = $backendProcess.Id
}

Start-Sleep -Seconds 2

if (-not $FrontendAlreadyRunning) {
    Write-Host "Dang chay frontend tai http://localhost:$FrontendPort"
    $frontendCommand = "`$env:VITE_API_BASE_URL='http://localhost:$BackendPort'; npm run dev -- --host 127.0.0.1 --port $FrontendPort"
    $frontendProcess = Start-Process powershell -WindowStyle Hidden -WorkingDirectory $FrontendDir -PassThru -ArgumentList @(
        "-NoExit",
        "-Command",
        $frontendCommand
    )
    $FrontendPid = $frontendProcess.Id
}

Write-DevState -BackendPort $BackendPort -FrontendPort $FrontendPort -BackendPid $BackendPid -FrontendPid $FrontendPid

Write-Host ""
Write-Host "Mo ung dung tai http://localhost:$FrontendPort" -ForegroundColor Green
Write-Host "Backend: http://127.0.0.1:$BackendPort"
Write-Host "Kiem tra trang thai: .\check-dev.ps1"
Write-Host "Tat tien trinh do script mo: .\stop-dev.ps1"
Write-Host "Hermes va n8n la tuy chon. Neu chua cau hinh, giao dien se hien huong dan sua loi thay vi bi crash."
