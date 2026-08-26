param(
    [int]$BackendPort = 0,
    [int]$FrontendPort = 0
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
. (Join-Path $Root "scripts\dev-provenance.ps1")

$StatePath = Join-Path $Root ".dev\dev-state.json"
$BackendDir = Get-PqgCanonicalPath (Join-Path $Root "backend")
$FrontendDir = Get-PqgCanonicalPath (Join-Path $Root "frontend")
$PythonExe = Get-PqgCanonicalPath (Join-Path $BackendDir ".venv\Scripts\python.exe")
$BackendEnv = Join-Path $BackendDir ".env"
$BackendPortWasExplicit = $PSBoundParameters.ContainsKey('BackendPort') -and $BackendPort -gt 0
$FrontendPortWasExplicit = $PSBoundParameters.ContainsKey('FrontendPort') -and $FrontendPort -gt 0
$ProofFailed = $false

function Test-HttpOk {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    } catch {
        return $false
    }
}

function Get-EffectiveBackendDbPath {
    if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { return $null }
    Push-Location $BackendDir
    try {
        $output = @(& $PythonExe -c "from app.settings import Settings; print(Settings().db_path_resolved)" 2>$null)
        if ($LASTEXITCODE -ne 0) { return $null }
        $value = @($output | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ }) | Select-Object -Last 1
        if ([string]::IsNullOrWhiteSpace([string]$value)) { return $null }
        return Get-PqgCanonicalPath ([string]$value)
    } finally {
        Pop-Location
    }
}

function Write-Proof {
    param(
        [bool]$Ok,
        [string]$Message
    )
    if ($Ok) {
        Write-Host "PROOF OK   $Message" -ForegroundColor Green
    } else {
        $script:ProofFailed = $true
        Write-Host "PROOF ERR  $Message" -ForegroundColor Red
    }
}

Write-Host "Kiem tra PQG Workspace" -ForegroundColor Cyan

if (Test-Path -LiteralPath $PythonExe -PathType Leaf) {
    Write-Host "OK  backend\.venv ton tai" -ForegroundColor Green
} else {
    Write-Host "ERR thieu backend\.venv" -ForegroundColor Red
}
if (Test-Path -LiteralPath (Join-Path $FrontendDir "node_modules") -PathType Container) {
    Write-Host "OK  frontend\node_modules ton tai" -ForegroundColor Green
} else {
    Write-Host "ERR thieu frontend\node_modules" -ForegroundColor Red
}
if (Test-Path -LiteralPath $BackendEnv -PathType Leaf) {
    Write-Host "OK  backend\.env ton tai" -ForegroundColor Green
} else {
    Write-Host "WARN chua co backend\.env" -ForegroundColor Yellow
}

$state = $null
try {
    $state = Read-PqgDevState -StatePath $StatePath
} catch {
    Write-Proof $false $_.Exception.Message
}

$currentSha = $null
try {
    $currentSha = Get-PqgCurrentSourceSha -RepositoryRoot $Root
} catch {
    Write-Proof $false $_.Exception.Message
}

$headerProof = $null
if ($null -eq $state) {
    Write-Proof $false '.dev\dev-state.json khong ton tai; HTTP health khong the thay the process provenance.'
} elseif ($null -ne $currentSha) {
    $headerProof = Test-PqgStateHeader -State $state -RepositoryRoot $Root -CurrentSourceSha $currentSha -RequireCurrentSource
    Write-Proof ($headerProof.status -eq 'Match') "repository/source: $($headerProof.reason)"
} else {
    Write-Proof $false 'Khong co current source SHA de doi chieu dev-state.'
}

$effectiveDbPath = Get-EffectiveBackendDbPath
if ($null -eq $effectiveDbPath) {
    Write-Proof $false 'Khong resolve duoc effective backend DB path tu Settings.'
}

if ($null -ne $state -and $null -ne $headerProof -and $headerProof.status -eq 'Match') {
    if (-not $BackendPortWasExplicit) {
        $candidate = ConvertTo-PqgInt $state.backend.port
        if ($null -ne $candidate -and $candidate -gt 0) { $BackendPort = $candidate }
    }
    if (-not $FrontendPortWasExplicit) {
        $candidate = ConvertTo-PqgInt $state.frontend.port
        if ($null -ne $candidate -and $candidate -gt 0) { $FrontendPort = $candidate }
    }

    $backendProofArgs = @{
        Record = $state.backend
        Role = 'backend'
        ExpectedWorkingDirectory = $BackendDir
        ExpectedPort = $BackendPort
        RequireDbPath = $true
    }
    if ($null -ne $effectiveDbPath) { $backendProofArgs.ExpectedDbPath = $effectiveDbPath }
    $backendProof = Test-PqgProcessRecord @backendProofArgs
    Write-Proof ($backendProof.status -eq 'Match') "backend process: $($backendProof.reason)"
    if ($backendProof.status -eq 'Match') {
        $backendPortOwned = Test-PqgPortOwnedByProcessTree -Port ([int]$state.backend.port) -RootPid ([int]$state.backend.pid)
        Write-Proof $backendPortOwned "backend port $($state.backend.port) thuoc recorded process tree"
        if ($null -ne $effectiveDbPath) {
            Write-Proof (Test-PqgPathEqual ([string]$state.backend.dbPath) $effectiveDbPath) "backend DB: $effectiveDbPath"
        }
    }

    $frontendProof = Test-PqgProcessRecord `
        -Record $state.frontend `
        -Role frontend `
        -ExpectedWorkingDirectory $FrontendDir `
        -ExpectedPort $FrontendPort
    Write-Proof ($frontendProof.status -eq 'Match') "frontend process: $($frontendProof.reason)"
    if ($frontendProof.status -eq 'Match') {
        $frontendPortOwned = Test-PqgPortOwnedByProcessTree -Port ([int]$state.frontend.port) -RootPid ([int]$state.frontend.pid)
        Write-Proof $frontendPortOwned "frontend port $($state.frontend.port) thuoc recorded process tree"
    }
}

if ($BackendPort -le 0) { $BackendPort = 8000 }
if ($FrontendPort -le 0) { $FrontendPort = 5173 }
$backendUrl = "http://127.0.0.1:$BackendPort"
$frontendUrl = "http://localhost:$FrontendPort"

Write-Host ""
Write-Host "HTTP/runtime health (khong phai identity proof):" -ForegroundColor Cyan
if (Test-HttpOk "$backendUrl/health") {
    Write-Host "HEALTH OK   backend phan hoi: $backendUrl" -ForegroundColor Green
    try {
        $runtime = Invoke-RestMethod "$backendUrl/api/runtime/status" -TimeoutSec 5
        Write-Host "HEALTH OK   DB status: $($runtime.db.status)" -ForegroundColor Green
        Write-Host "HEALTH INFO runtime assistant status: $($runtime.hermes.status)"
        Write-Host "HEALTH INFO n8n configured: $($runtime.n8n.configured)"
    } catch {
        Write-Host "HEALTH WARN backend chay nhung runtime status khong doc duoc" -ForegroundColor Yellow
    }
} else {
    Write-Host "HEALTH ERR  backend chua phan hoi tai $backendUrl" -ForegroundColor Red
}

if (Test-HttpOk $frontendUrl) {
    Write-Host "HEALTH OK   frontend phan hoi: $frontendUrl" -ForegroundColor Green
} else {
    Write-Host "HEALTH ERR  frontend chua phan hoi tai $frontendUrl" -ForegroundColor Red
}

Write-Host ""
Write-Host "Mo app: $frontendUrl"
if ($ProofFailed) {
    Write-Host 'Identity proof KHONG DAT. Khong duoc dung HTTP health de suy dien dung repo/process/DB.' -ForegroundColor Red
    exit 1
}
Write-Host 'Identity proof DAT; HTTP health duoc bao cao rieng.' -ForegroundColor Green
