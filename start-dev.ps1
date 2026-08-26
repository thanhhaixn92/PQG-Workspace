param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._:@-]{0,199}$')]
    [string]$LocalActorSubject = "local-dev-user",
    [switch]$Fresh,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$DevDir = Join-Path $Root ".dev"
$StatePath = Join-Path $DevDir "dev-state.json"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
$BackendEnv = Join-Path $BackendDir ".env"
. (Join-Path $Root "scripts\dev-provenance.ps1")

$BackendCommandIdentity = "uvicorn app.main:app"
$FrontendCommandIdentity = "npm run dev"
$SourceSha = Get-PqgCurrentSourceSha -RepositoryRoot $Root
$PowerShellExe = Get-PqgPowerShellExecutable

function Test-PortAvailable {
    param([int]$Port)
    return -not [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
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

function Get-ReusableRecord {
    param(
        [object]$State,
        [Parameter(Mandatory = $true)][ValidateSet("backend", "frontend")][string]$Role,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$IdentityMarker,
        [string]$DbPath
    )

    if ($null -eq $State) { return $null }
    $header = Test-PqgStateHeader -State $State -RepositoryRoot $Root -CurrentSourceSha $SourceSha -RequireCurrentSource
    if ($header.status -ne "Match") { return $null }

    if ($Role -eq "backend") {
        $proof = Test-PqgProcessRecord `
            -Record $State.backend `
            -Role backend `
            -ExpectedWorkingDirectory $BackendDir `
            -ExpectedCommand $BackendCommandIdentity `
            -ExpectedIdentityMarker $IdentityMarker `
            -ExpectedExecutable $PowerShellExe `
            -ExpectedPort $Port `
            -ExpectedDbPath $DbPath `
            -RequireDbPath
        $record = $State.backend
    } else {
        $proof = Test-PqgProcessRecord `
            -Record $State.frontend `
            -Role frontend `
            -ExpectedWorkingDirectory $FrontendDir `
            -ExpectedCommand $FrontendCommandIdentity `
            -ExpectedIdentityMarker $IdentityMarker `
            -ExpectedExecutable $PowerShellExe `
            -ExpectedPort $Port
        $record = $State.frontend
    }

    if ($proof.status -ne "Match") { return $null }
    if (-not (Test-PqgPortOwnedByProcessTree -Port $Port -RootProcessId ([int]$record.pid))) {
        return $null
    }
    return $record
}

function Write-DevState {
    param(
        [Parameter(Mandatory = $true)][object]$BackendRecord,
        [Parameter(Mandatory = $true)][object]$FrontendRecord
    )

    if (-not (Test-Path -LiteralPath $DevDir)) {
        New-Item -ItemType Directory -Path $DevDir | Out-Null
    }

    $payload = [ordered]@{
        schemaVersion = 2
        repositoryRoot = $Root
        sourceSha = $SourceSha
        startedAt = (Get-Date).ToUniversalTime().ToString("o")
        backend = $BackendRecord
        frontend = $FrontendRecord
    }
    $payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

Write-Host "Khoi dong moi truong phat trien PQG Workspace" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $PythonExe)) {
    Write-Host "Chua co moi truong Python: backend\.venv" -ForegroundColor Yellow
    Write-Host "Tao bang lenh: cd backend; py -3.11 -m venv .venv; .venv\Scripts\pip.exe install -e `".[dev]`""
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "Chua cai dependency frontend: frontend\node_modules" -ForegroundColor Yellow
    Write-Host "Cai bang lenh: cd frontend; npm install"
    exit 1
}

$BackendDbPath = Get-PqgConfiguredDbPath -BackendDirectory $BackendDir -PythonExecutable $PythonExe
$BackendIdentityMarker = Get-PqgIdentityMarker -Role backend -RepositoryRoot $Root -SourceSha $SourceSha
$FrontendIdentityMarker = Get-PqgIdentityMarker -Role frontend -RepositoryRoot $Root -SourceSha $SourceSha

if (-not (Test-Path -LiteralPath $BackendEnv)) {
    Write-Host "Chua co backend\.env" -ForegroundColor Yellow
    Write-Host "Tao tu template bang lenh: Copy-Item backend\.env.example backend\.env"
} else {
    Write-Host "OK  backend\.env ton tai; dev-state chi ghi non-secret provenance." -ForegroundColor Green
}

$state = $null
try {
    $state = Read-PqgDevState -StatePath $StatePath
} catch {
    Write-Host "WARN dev-state hien tai khong hop le; se khong reuse bat ky process nao." -ForegroundColor Yellow
}

$BackendRecord = $null
$FrontendRecord = $null

if (-not (Test-PortAvailable $BackendPort)) {
    $reusable = $null
    if (-not $Fresh) {
        $reusable = Get-ReusableRecord -State $state -Role backend -Port $BackendPort -IdentityMarker $BackendIdentityMarker -DbPath $BackendDbPath
    }
    if ($null -ne $reusable -and (Test-HttpOk "http://127.0.0.1:$BackendPort/health")) {
        $BackendRecord = $reusable
        Write-Host "Backend dang chay va provenance khop tai http://127.0.0.1:$BackendPort" -ForegroundColor Green
    } else {
        $oldPort = $BackendPort
        $BackendPort = Find-AvailablePort ($BackendPort + 1)
        Write-Host "Cong backend $oldPort dang ban nhung identity khong duoc chung minh. Khong reuse; dung cong moi: $BackendPort" -ForegroundColor Yellow
    }
}

if (-not (Test-PortAvailable $FrontendPort)) {
    $reusable = $null
    if (-not $Fresh) {
        $reusable = Get-ReusableRecord -State $state -Role frontend -Port $FrontendPort -IdentityMarker $FrontendIdentityMarker
    }
    if ($null -ne $reusable -and (Test-HttpOk "http://localhost:$FrontendPort")) {
        $FrontendRecord = $reusable
        Write-Host "Frontend dang chay va provenance khop tai http://localhost:$FrontendPort" -ForegroundColor Green
    } else {
        $oldPort = $FrontendPort
        $FrontendPort = Find-AvailablePort ($FrontendPort + 1)
        Write-Host "Cong frontend $oldPort dang ban nhung identity khong duoc chung minh. Khong reuse; dung cong moi: $FrontendPort" -ForegroundColor Yellow
    }
}

if ($null -eq $BackendRecord) {
    Write-Host "Dang chay backend tai http://127.0.0.1:$BackendPort"
    $reloadFlag = if ($NoReload) { "" } else { " --reload" }
    $safeActor = $LocalActorSubject -replace "'", "''"
    $backendCommand = "`$pqgIdentity='$BackendIdentityMarker'; `$env:CORS_ORIGINS='http://localhost:$FrontendPort'; `$env:LOCAL_ACTOR_SUBJECT='$safeActor'; .\.venv\Scripts\python.exe -m uvicorn app.main:app$reloadFlag --host 127.0.0.1 --port $BackendPort"
    $backendProcess = Start-Process powershell -WindowStyle Hidden -WorkingDirectory $BackendDir -PassThru -ArgumentList @(
        "-NoExit",
        "-Command",
        $backendCommand
    )
    $BackendRecord = New-PqgProcessRecord `
        -ProcessId $backendProcess.Id `
        -WorkingDirectory $BackendDir `
        -Command $BackendCommandIdentity `
        -IdentityMarker $BackendIdentityMarker `
        -Port $BackendPort `
        -DbPath $BackendDbPath
}

Start-Sleep -Seconds 2

if ($null -eq $FrontendRecord) {
    Write-Host "Dang chay frontend tai http://localhost:$FrontendPort"
    $frontendCommand = "`$pqgIdentity='$FrontendIdentityMarker'; Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue; `$env:VITE_API_PROXY_TARGET='http://127.0.0.1:$BackendPort'; npm run dev -- --host 127.0.0.1 --port $FrontendPort"
    $frontendProcess = Start-Process powershell -WindowStyle Hidden -WorkingDirectory $FrontendDir -PassThru -ArgumentList @(
        "-NoExit",
        "-Command",
        $frontendCommand
    )
    $FrontendRecord = New-PqgProcessRecord `
        -ProcessId $frontendProcess.Id `
        -WorkingDirectory $FrontendDir `
        -Command $FrontendCommandIdentity `
        -IdentityMarker $FrontendIdentityMarker `
        -Port $FrontendPort
}

Write-DevState -BackendRecord $BackendRecord -FrontendRecord $FrontendRecord

Write-Host ""
Write-Host "Mo ung dung tai http://localhost:$FrontendPort" -ForegroundColor Green
Write-Host "Backend: http://127.0.0.1:$BackendPort"
Write-Host "DB: $BackendDbPath"
Write-Host "Source SHA: $SourceSha"
Write-Host "Kiem tra provenance va health: .\check-dev.ps1"
Write-Host "Tat chi process co identity khop: .\stop-dev.ps1"
