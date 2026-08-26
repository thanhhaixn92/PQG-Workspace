param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    # Restrict this local-only subject to a command-safe identifier before it
    # is passed to the child PowerShell process. The backend independently
    # validates the configured value and never accepts it from browser input.
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._:@-]{0,199}$')]
    [string]$LocalActorSubject = "local-dev-user",
    [switch]$Fresh,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
. (Join-Path $Root "scripts\dev-provenance.ps1")

$BackendDir = Get-PqgCanonicalPath (Join-Path $Root "backend")
$FrontendDir = Get-PqgCanonicalPath (Join-Path $Root "frontend")
$DevDir = Join-Path $Root ".dev"
$StatePath = Join-Path $DevDir "dev-state.json"
$PythonExe = Get-PqgCanonicalPath (Join-Path $BackendDir ".venv\Scripts\python.exe")
$BackendEnv = Join-Path $BackendDir ".env"
$BackendPortWasExplicit = $PSBoundParameters.ContainsKey('BackendPort')
$FrontendPortWasExplicit = $PSBoundParameters.ContainsKey('FrontendPort')

function Test-PortAvailable {
    param([int]$Port)
    return -not (Test-PqgPortListener -Port $Port)
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

function Get-EffectiveBackendDbPath {
    Push-Location $BackendDir
    try {
        $output = @(& $PythonExe -c "from app.settings import Settings; print(Settings().db_path_resolved)" 2>$null)
        if ($LASTEXITCODE -ne 0) {
            throw 'Backend settings could not resolve DB_PATH.'
        }
        $value = @($output | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ }) | Select-Object -Last 1
        if ([string]::IsNullOrWhiteSpace([string]$value)) {
            throw 'Backend settings returned an empty DB path.'
        }
        return Get-PqgCanonicalPath ([string]$value)
    } finally {
        Pop-Location
    }
}

function Test-RecordedRootPidsAbsent {
    param([object]$State)

    if ($null -eq $State) { return $true }
    $rawPids = @()
    $foundPidField = $false
    if ((Test-PqgHasProperty $State 'backend') -and (Test-PqgHasProperty $State.backend 'pid')) {
        $rawPids += $State.backend.pid
        $foundPidField = $true
    } elseif (Test-PqgHasProperty $State 'backendPid') {
        $rawPids += $State.backendPid
        $foundPidField = $true
    }
    if ((Test-PqgHasProperty $State 'frontend') -and (Test-PqgHasProperty $State.frontend 'pid')) {
        $rawPids += $State.frontend.pid
        $foundPidField = $true
    } elseif (Test-PqgHasProperty $State 'frontendPid') {
        $rawPids += $State.frontendPid
        $foundPidField = $true
    }
    if (-not $foundPidField) { return $false }

    foreach ($rawPid in $rawPids) {
        $pidValue = ConvertTo-PqgInt $rawPid
        if ($null -eq $pidValue) { return $false }
        if ($pidValue -gt 0 -and $null -ne (Get-PqgProcessSnapshot -Pid $pidValue)) {
            return $false
        }
    }
    return $true
}

function Write-DevState {
    param(
        [Parameter(Mandatory = $true)][string]$SourceSha,
        [Parameter(Mandatory = $true)][object]$Backend,
        [Parameter(Mandatory = $true)][object]$Frontend
    )

    if (-not (Test-Path -LiteralPath $DevDir)) {
        New-Item -ItemType Directory -Path $DevDir | Out-Null
    }
    $state = [ordered]@{
        schemaVersion = 2
        repositoryRoot = $Root
        sourceSha = $SourceSha
        startedAt = (Get-Date).ToUniversalTime().ToString('o')
        backend = $Backend
        frontend = $Frontend
    }
    $state | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

function Stop-NewWrapper {
    param([int]$Pid)
    if ($Pid -le 0) { return }
    $process = Get-Process -Id $Pid -ErrorAction SilentlyContinue
    if ($process) {
        & taskkill.exe /PID $Pid /T /F 2>$null | Out-Null
    }
}

Write-Host "Khoi dong moi truong phat trien PQG Workspace" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    Write-Host "Chua co moi truong Python: backend\.venv" -ForegroundColor Yellow
    Write-Host "Tao bang lenh: cd backend; py -3.11 -m venv .venv; .venv\Scripts\pip.exe install -e `".[dev]`""
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "node_modules") -PathType Container)) {
    Write-Host "Chua cai dependency frontend: frontend\node_modules" -ForegroundColor Yellow
    Write-Host "Cai bang lenh: cd frontend; npm install"
    exit 1
}

if (-not (Test-Path -LiteralPath $BackendEnv -PathType Leaf)) {
    Write-Host "Chua co backend\.env" -ForegroundColor Yellow
    Write-Host "Tao tu template bang lenh: Copy-Item backend\.env.example backend\.env"
} else {
    Write-Host "OK  backend\.env ton tai; dev-state se khong luu gia tri secret." -ForegroundColor Green
}

$SourceSha = Get-PqgCurrentSourceSha -RepositoryRoot $Root
$BackendDbPath = Get-EffectiveBackendDbPath
$ExistingState = $null
if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
    try {
        $ExistingState = Read-PqgDevState -StatePath $StatePath
    } catch {
        throw "Khong the doc provenance trong .dev\dev-state.json. Tu choi overwrite state khong xac minh duoc. $($_.Exception.Message)"
    }
}

$BackendAlreadyRunning = $false
$FrontendAlreadyRunning = $false
$BackendRecord = $null
$FrontendRecord = $null

if ($null -ne $ExistingState) {
    $headerProof = Test-PqgStateHeader -State $ExistingState -RepositoryRoot $Root -CurrentSourceSha $SourceSha -RequireCurrentSource
    if ($headerProof.status -ne 'Match') {
        if (-not (Test-RecordedRootPidsAbsent -State $ExistingState)) {
            throw "Dev-state khong khop checkout hien tai ($($headerProof.reason)) va recorded PID chua duoc chung minh la da dung. Tu choi reuse/overwrite."
        }
        Write-Host "WARN dev-state cu khong duoc reuse: $($headerProof.reason). Recorded root PID deu khong con chay." -ForegroundColor Yellow
        $ExistingState = $null
    }
}

if ($null -ne $ExistingState) {
    if (-not $BackendPortWasExplicit) { $BackendPort = [int]$ExistingState.backend.port }
    if (-not $FrontendPortWasExplicit) { $FrontendPort = [int]$ExistingState.frontend.port }

    $backendProof = Test-PqgProcessRecord `
        -Record $ExistingState.backend `
        -Role backend `
        -ExpectedWorkingDirectory $BackendDir `
        -ExpectedPort $BackendPort `
        -ExpectedDbPath $BackendDbPath `
        -RequireDbPath
    $frontendProof = Test-PqgProcessRecord `
        -Record $ExistingState.frontend `
        -Role frontend `
        -ExpectedWorkingDirectory $FrontendDir `
        -ExpectedPort $FrontendPort

    foreach ($proofItem in @(
        [pscustomobject]@{ name = 'backend'; proof = $backendProof },
        [pscustomobject]@{ name = 'frontend'; proof = $frontendProof }
    )) {
        if ($proofItem.proof.status -in @('Mismatch', 'Incomplete')) {
            throw "Tu choi reuse/overwrite $($proofItem.name): $($proofItem.proof.reason)"
        }
    }

    if ($backendProof.status -eq 'Match') {
        if ($Fresh) {
            throw 'Backend recorded van dang chay va identity khop. -Fresh khong duoc phep orphan process; hay chay stop-dev.ps1 truoc.'
        }
        if (-not (Test-PqgPortOwnedByProcessTree -Port $BackendPort -RootPid ([int]$ExistingState.backend.pid))) {
            throw 'Backend PID identity khop nhung recorded port khong thuoc process tree do. Tu choi reuse.'
        }
        if (-not (Test-HttpOk "http://127.0.0.1:$BackendPort/health")) {
            throw 'Backend PID/port identity khop nhung health khong dat. Tu choi orphan/reuse im lang; hay stop an toan va khoi dong lai.'
        }
        $BackendAlreadyRunning = $true
        $BackendRecord = $ExistingState.backend
        Write-Host "Reuse backend da duoc chung minh tai http://127.0.0.1:$BackendPort" -ForegroundColor Green
    }

    if ($frontendProof.status -eq 'Match') {
        if ($Fresh) {
            throw 'Frontend recorded van dang chay va identity khop. -Fresh khong duoc phep orphan process; hay chay stop-dev.ps1 truoc.'
        }
        if (-not (Test-PqgPortOwnedByProcessTree -Port $FrontendPort -RootPid ([int]$ExistingState.frontend.pid))) {
            throw 'Frontend PID identity khop nhung recorded port khong thuoc process tree do. Tu choi reuse.'
        }
        if (-not (Test-HttpOk "http://localhost:$FrontendPort")) {
            throw 'Frontend PID/port identity khop nhung HTTP health khong dat. Tu choi orphan/reuse im lang; hay stop an toan va khoi dong lai.'
        }
        $FrontendAlreadyRunning = $true
        $FrontendRecord = $ExistingState.frontend
        Write-Host "Reuse frontend da duoc chung minh tai http://localhost:$FrontendPort" -ForegroundColor Green
    }
}

if (-not $BackendAlreadyRunning -and -not (Test-PortAvailable $BackendPort)) {
    $oldPort = $BackendPort
    $BackendPort = Find-AvailablePort ($BackendPort + 1)
    Write-Host "Cong backend $oldPort dang duoc process khac su dung. Khong adopt theo health; dung cong moi: $BackendPort" -ForegroundColor Yellow
}
if (-not $FrontendAlreadyRunning -and -not (Test-PortAvailable $FrontendPort)) {
    $oldPort = $FrontendPort
    $FrontendPort = Find-AvailablePort ($FrontendPort + 1)
    Write-Host "Cong frontend $oldPort dang duoc process khac su dung. Khong adopt theo health; dung cong moi: $FrontendPort" -ForegroundColor Yellow
}

$NewBackendPid = 0
$NewFrontendPid = 0
try {
    if (-not $BackendAlreadyRunning) {
        Write-Host "Dang chay backend tai http://127.0.0.1:$BackendPort"
        $reloadFlag = if ($NoReload) { "" } else { " --reload" }
        $BackendCommandIdentity = ".\.venv\Scripts\python.exe -m uvicorn app.main:app$reloadFlag --host 127.0.0.1 --port $BackendPort"
        $BackendIdentityMarker = "PQG-DEV|backend|repo=$Root|sha=$SourceSha|cwd=$BackendDir|port=$BackendPort|db=$BackendDbPath"
        $markerLiteral = ConvertTo-PqgSingleQuotedLiteral $BackendIdentityMarker
        $dbLiteral = ConvertTo-PqgSingleQuotedLiteral $BackendDbPath
        $cwdLiteral = ConvertTo-PqgSingleQuotedLiteral $BackendDir
        $backendCommand = "`$env:PQG_DEV_IDENTITY='$markerLiteral'; `$env:DB_PATH='$dbLiteral'; `$env:CORS_ORIGINS='http://localhost:$FrontendPort'; `$env:LOCAL_ACTOR_SUBJECT='$LocalActorSubject'; Set-Location -LiteralPath '$cwdLiteral'; $BackendCommandIdentity"
        $backendProcess = Start-Process powershell -WindowStyle Hidden -WorkingDirectory $BackendDir -PassThru -ArgumentList @(
            "-NoExit",
            "-Command",
            $backendCommand
        )
        $NewBackendPid = $backendProcess.Id
        $BackendRecord = New-PqgProcessRecord `
            -Pid $NewBackendPid `
            -WorkingDirectory $BackendDir `
            -Command $BackendCommandIdentity `
            -IdentityMarker $BackendIdentityMarker `
            -Port $BackendPort `
            -DbPath $BackendDbPath
    }

    Start-Sleep -Seconds 2

    if (-not $FrontendAlreadyRunning) {
        Write-Host "Dang chay frontend tai http://localhost:$FrontendPort"
        $FrontendCommandIdentity = "npm run dev -- --host 127.0.0.1 --port $FrontendPort"
        $FrontendIdentityMarker = "PQG-DEV|frontend|repo=$Root|sha=$SourceSha|cwd=$FrontendDir|port=$FrontendPort"
        $markerLiteral = ConvertTo-PqgSingleQuotedLiteral $FrontendIdentityMarker
        $cwdLiteral = ConvertTo-PqgSingleQuotedLiteral $FrontendDir
        $frontendCommand = "`$env:PQG_DEV_IDENTITY='$markerLiteral'; Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue; `$env:VITE_API_PROXY_TARGET='http://127.0.0.1:$BackendPort'; Set-Location -LiteralPath '$cwdLiteral'; $FrontendCommandIdentity"
        $frontendProcess = Start-Process powershell -WindowStyle Hidden -WorkingDirectory $FrontendDir -PassThru -ArgumentList @(
            "-NoExit",
            "-Command",
            $frontendCommand
        )
        $NewFrontendPid = $frontendProcess.Id
        $FrontendRecord = New-PqgProcessRecord `
            -Pid $NewFrontendPid `
            -WorkingDirectory $FrontendDir `
            -Command $FrontendCommandIdentity `
            -IdentityMarker $FrontendIdentityMarker `
            -Port $FrontendPort
    }

    if ($null -eq $BackendRecord -or $null -eq $FrontendRecord) {
        throw 'Cannot write complete dev-state because process provenance is incomplete.'
    }
    Write-DevState -SourceSha $SourceSha -Backend $BackendRecord -Frontend $FrontendRecord
} catch {
    if ($NewFrontendPid -gt 0) { Stop-NewWrapper -Pid $NewFrontendPid }
    if ($NewBackendPid -gt 0) { Stop-NewWrapper -Pid $NewBackendPid }
    throw
}

Write-Host ""
Write-Host "Mo ung dung tai http://localhost:$FrontendPort" -ForegroundColor Green
Write-Host "Backend: http://127.0.0.1:$BackendPort"
Write-Host "Provenance: .dev\dev-state.json (schema v2, source $SourceSha)"
Write-Host "Kiem tra identity va health rieng: .\check-dev.ps1"
Write-Host "Tat chi process duoc chung minh: .\stop-dev.ps1"
