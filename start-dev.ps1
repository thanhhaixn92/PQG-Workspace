param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._:@-]{0,199}$')]
    [string]$LocalActorSubject = "local-dev-user",
    [string]$DevStatePath,
    [switch]$Fresh,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$StatePath = if ($DevStatePath) { [System.IO.Path]::GetFullPath($DevStatePath) } else { Join-Path $Root ".dev\dev-state.json" }
$DevDir = Split-Path -Parent $StatePath
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
$BackendEnv = Join-Path $BackendDir ".env"
. (Join-Path $Root "scripts\dev-provenance.ps1")

$BackendPortWasExplicit = $PSBoundParameters.ContainsKey('BackendPort')
$FrontendPortWasExplicit = $PSBoundParameters.ContainsKey('FrontendPort')
$SourceSha = Get-PqgCurrentSourceSha -RepositoryRoot $Root
$PowerShellExe = Get-PqgPowerShellExecutable
$BackendIdentityMarker = Get-PqgIdentityMarker -Role backend -RepositoryRoot $Root -SourceSha $SourceSha
$FrontendIdentityMarker = Get-PqgIdentityMarker -Role frontend -RepositoryRoot $Root -SourceSha $SourceSha

function ConvertTo-SingleQuotedLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return ($Value -replace "'", "''")
}

function Test-PortAvailable {
    param([int]$Port)
    return -not [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Test-HttpOk {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    } catch { return $false }
}

function Find-AvailablePort {
    param([int]$StartPort,[int]$MaxAttempts = 20)
    for ($offset = 0; $offset -lt $MaxAttempts; $offset++) {
        $candidate = $StartPort + $offset
        if (Test-PortAvailable $candidate) { return $candidate }
    }
    throw "Khong tim thay cong trong tu $StartPort den $($StartPort + $MaxAttempts - 1)."
}

function Write-DevState {
    param([object]$BackendRecord,[object]$FrontendRecord)
    if (-not (Test-Path -LiteralPath $DevDir)) { New-Item -ItemType Directory -Path $DevDir -Force | Out-Null }
    [ordered]@{
        schemaVersion = 2
        repositoryRoot = $Root
        sourceSha = $SourceSha
        startedAt = (Get-Date).ToUniversalTime().ToString('o')
        backend = $BackendRecord
        frontend = $FrontendRecord
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $StatePath -Encoding UTF8
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

$BackendDbPath = Get-PqgConfiguredDbPath -BackendDirectory $BackendDir -PythonExecutable $PythonExe
if (Test-Path -LiteralPath $BackendEnv -PathType Leaf) {
    Write-Host "OK  backend\.env ton tai; dev-state chi ghi non-secret provenance." -ForegroundColor Green
} else {
    Write-Host "WARN chua co backend\.env; backend se dung safe defaults/env hien tai." -ForegroundColor Yellow
}

$state = $null
if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
    try { $state = Read-PqgDevState -StatePath $StatePath }
    catch { throw "Dev-state ton tai nhung khong doc duoc. Tu choi overwrite provenance khong xac minh duoc: $($_.Exception.Message)" }
}

$BackendRecord = $null
$FrontendRecord = $null
$recordedBackendPort = 0
$recordedFrontendPort = 0
$backendProof = $null
$frontendProof = $null

if ($null -ne $state) {
    $headerProof = Test-PqgStateHeader -State $state -RepositoryRoot $Root -CurrentSourceSha $SourceSha -RequireCurrentSource
    if ($headerProof.status -ne 'Match') { throw "Dev-state khong khop checkout hien tai: $($headerProof.reason). Tu choi reuse va overwrite." }
    if (-not (Test-PqgHasProperty $state.backend 'reload') -or $state.backend.reload -isnot [bool]) { throw 'Dev-state backend.reload bi thieu/khong hop le.' }
    try { $recordedBackendPort=[int]$state.backend.port; $recordedFrontendPort=[int]$state.frontend.port }
    catch { throw 'Dev-state co port khong hop le. Tu choi overwrite.' }

    $backendCommandIdentity = Get-PqgBackendCommandIdentity -RepositoryRoot $Root -SourceSha $SourceSha -BackendDirectory $BackendDir -Port $recordedBackendPort -DbPath $BackendDbPath -Reload ([bool]$state.backend.reload)
    $frontendCommandIdentity = Get-PqgFrontendCommandIdentity -RepositoryRoot $Root -SourceSha $SourceSha -FrontendDirectory $FrontendDir -Port $recordedFrontendPort -BackendPort $recordedBackendPort
    $backendProof = Test-PqgProcessRecord -Record $state.backend -Role backend -ExpectedWorkingDirectory $BackendDir -ExpectedCommand $backendCommandIdentity -ExpectedIdentityMarker $BackendIdentityMarker -ExpectedExecutable $PowerShellExe -ExpectedPort $recordedBackendPort -ExpectedDbPath $BackendDbPath -RequireDbPath
    $frontendProof = Test-PqgProcessRecord -Record $state.frontend -Role frontend -ExpectedWorkingDirectory $FrontendDir -ExpectedCommand $frontendCommandIdentity -ExpectedIdentityMarker $FrontendIdentityMarker -ExpectedExecutable $PowerShellExe -ExpectedPort $recordedFrontendPort

    if ($backendProof.status -in @('Mismatch','Incomplete')) { throw "Tu choi start/reuse/overwrite backend state: $($backendProof.reason)" }
    if ($frontendProof.status -in @('Mismatch','Incomplete')) { throw "Tu choi start/reuse/overwrite frontend state: $($frontendProof.reason)" }
    if ($Fresh -and ($backendProof.status -eq 'Match' -or $frontendProof.status -eq 'Match')) { throw '-Fresh khong duoc orphan recorded process dang chay. Hay chay stop-dev.ps1 truoc.' }
    if ($NoReload -and [bool]$state.backend.reload -and $backendProof.status -eq 'Match') { throw 'Invocation -NoReload khong duoc reuse backend recorded voi reload.' }

    if ($backendProof.status -eq 'Match') {
        if ($BackendPortWasExplicit -and $BackendPort -ne $recordedBackendPort) { throw "Backend recorded dang chay o port $recordedBackendPort; tu choi port $BackendPort." }
        $BackendPort=$recordedBackendPort
        if (-not (Test-PqgPortOwnedByProcessTree -Port $BackendPort -RootProcessId ([int]$state.backend.pid))) { throw 'Backend identity khop nhung recorded port khong thuoc process tree.' }
        if (-not (Test-HttpOk "http://127.0.0.1:$BackendPort/health")) { throw 'Backend identity khop nhung health khong dat. Tu choi reuse.' }
        $BackendRecord=$state.backend
        Write-Host "Reuse backend da duoc chung minh tai http://127.0.0.1:$BackendPort" -ForegroundColor Green
    } elseif (-not $BackendPortWasExplicit) { $BackendPort=$recordedBackendPort }

    if ($frontendProof.status -eq 'Match') {
        if ($FrontendPortWasExplicit -and $FrontendPort -ne $recordedFrontendPort) { throw "Frontend recorded dang chay o port $recordedFrontendPort; tu choi port $FrontendPort." }
        if ($BackendPortWasExplicit -and $BackendPort -ne $recordedBackendPort) { throw "Frontend recorded dang proxy toi backend port $recordedBackendPort; tu choi reuse voi backend port $BackendPort." }
        $FrontendPort=$recordedFrontendPort
        if (-not (Test-PqgPortOwnedByProcessTree -Port $FrontendPort -RootProcessId ([int]$state.frontend.pid))) { throw 'Frontend identity khop nhung recorded port khong thuoc process tree.' }
        if (-not (Test-HttpOk "http://localhost:$FrontendPort")) { throw 'Frontend identity khop nhung health khong dat. Tu choi reuse.' }
        $FrontendRecord=$state.frontend
        Write-Host "Reuse frontend da duoc chung minh tai http://localhost:$FrontendPort" -ForegroundColor Green
    } elseif (-not $FrontendPortWasExplicit) { $FrontendPort=$recordedFrontendPort }
}

if ($null -eq $BackendRecord -and -not (Test-PortAvailable $BackendPort)) {
    if ($null -ne $FrontendRecord) { throw "Backend port $BackendPort dang ban trong khi frontend reusable van bind toi port nay. Tu choi doi port im lang; hay stop-dev.ps1 truoc." }
    $oldPort=$BackendPort; $BackendPort=Find-AvailablePort ($BackendPort+1)
    Write-Host "Cong backend $oldPort dang ban nhung khong co reusable provenance. Khong adopt; dung cong moi: $BackendPort" -ForegroundColor Yellow
}
if ($null -eq $FrontendRecord -and -not (Test-PortAvailable $FrontendPort)) {
    $oldPort=$FrontendPort; $FrontendPort=Find-AvailablePort ($FrontendPort+1)
    Write-Host "Cong frontend $oldPort dang ban nhung khong co reusable provenance. Khong adopt; dung cong moi: $FrontendPort" -ForegroundColor Yellow
}

$NewBackendProcessId=0
$NewFrontendProcessId=0
try {
    if ($null -eq $BackendRecord) {
        $reload=-not $NoReload
        $backendCommandIdentity=Get-PqgBackendCommandIdentity -RepositoryRoot $Root -SourceSha $SourceSha -BackendDirectory $BackendDir -Port $BackendPort -DbPath $BackendDbPath -Reload $reload
        $reloadFlag=if ($reload) { ' --reload' } else { '' }
        $safeActor=ConvertTo-SingleQuotedLiteral $LocalActorSubject
        $safeIdentity=ConvertTo-SingleQuotedLiteral $BackendIdentityMarker
        $safeCommandIdentity=ConvertTo-SingleQuotedLiteral $backendCommandIdentity
        $safeDb=ConvertTo-SingleQuotedLiteral $BackendDbPath
        $safeBackendDir=ConvertTo-SingleQuotedLiteral $BackendDir
        $backendCommand="`$pqgIdentity='$safeIdentity'; `$pqgCommandIdentity='$safeCommandIdentity'; `$env:DB_PATH='$safeDb'; `$env:CORS_ORIGINS='http://localhost:$FrontendPort'; `$env:LOCAL_ACTOR_SUBJECT='$safeActor'; Set-Location -LiteralPath '$safeBackendDir'; .\.venv\Scripts\python.exe -m uvicorn app.main:app$reloadFlag --host 127.0.0.1 --port $BackendPort"
        Write-Host "Dang chay backend tai http://127.0.0.1:$BackendPort"
        $backendProcess=Start-Process $PowerShellExe -WindowStyle Hidden -WorkingDirectory $BackendDir -PassThru -ArgumentList @('-NoExit','-Command',$backendCommand)
        $NewBackendProcessId=$backendProcess.Id
        $BackendRecord=New-PqgProcessRecord -ProcessId $NewBackendProcessId -WorkingDirectory $BackendDir -Command $backendCommandIdentity -IdentityMarker $BackendIdentityMarker -Port $BackendPort -DbPath $BackendDbPath
        $BackendRecord | Add-Member -NotePropertyName reload -NotePropertyValue $reload -Force
    }

    Start-Sleep -Seconds 2

    if ($null -eq $FrontendRecord) {
        $frontendCommandIdentity=Get-PqgFrontendCommandIdentity -RepositoryRoot $Root -SourceSha $SourceSha -FrontendDirectory $FrontendDir -Port $FrontendPort -BackendPort $BackendPort
        $safeIdentity=ConvertTo-SingleQuotedLiteral $FrontendIdentityMarker
        $safeCommandIdentity=ConvertTo-SingleQuotedLiteral $frontendCommandIdentity
        $safeFrontendDir=ConvertTo-SingleQuotedLiteral $FrontendDir
        $frontendCommand="`$pqgIdentity='$safeIdentity'; `$pqgCommandIdentity='$safeCommandIdentity'; Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue; `$env:VITE_API_PROXY_TARGET='http://127.0.0.1:$BackendPort'; Set-Location -LiteralPath '$safeFrontendDir'; npm run dev -- --host 127.0.0.1 --port $FrontendPort"
        Write-Host "Dang chay frontend tai http://localhost:$FrontendPort"
        $frontendProcess=Start-Process $PowerShellExe -WindowStyle Hidden -WorkingDirectory $FrontendDir -PassThru -ArgumentList @('-NoExit','-Command',$frontendCommand)
        $NewFrontendProcessId=$frontendProcess.Id
        $FrontendRecord=New-PqgProcessRecord -ProcessId $NewFrontendProcessId -WorkingDirectory $FrontendDir -Command $frontendCommandIdentity -IdentityMarker $FrontendIdentityMarker -Port $FrontendPort
    }

    Write-DevState -BackendRecord $BackendRecord -FrontendRecord $FrontendRecord
} catch {
    if ($NewFrontendProcessId -gt 0) { & taskkill.exe /PID $NewFrontendProcessId /T /F 2>$null | Out-Null }
    if ($NewBackendProcessId -gt 0) { & taskkill.exe /PID $NewBackendProcessId /T /F 2>$null | Out-Null }
    throw
}

Write-Host ""
Write-Host "Mo ung dung tai http://localhost:$FrontendPort" -ForegroundColor Green
Write-Host "Backend: http://127.0.0.1:$BackendPort"
Write-Host "DB: $BackendDbPath"
Write-Host "Source SHA: $SourceSha"
Write-Host "Dev-state: $StatePath"
Write-Host "Kiem tra provenance va health: .\check-dev.ps1"
Write-Host "Tat chi process co identity khop: .\stop-dev.ps1"
