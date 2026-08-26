param(
    [int]$BackendPort = 0,
    [int]$FrontendPort = 0,
    [string]$DevStatePath
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
. (Join-Path $Root "scripts\dev-provenance.ps1")

$StatePath = if ($DevStatePath) { [System.IO.Path]::GetFullPath($DevStatePath) } else { Join-Path $Root ".dev\dev-state.json" }
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
$BackendEnv = Join-Path $BackendDir ".env"
$ProofFailed = $false

function Test-HttpOk {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    } catch { return $false }
}

function Write-Proof {
    param([bool]$Ok,[string]$Message)
    if ($Ok) { Write-Host "PROOF OK   $Message" -ForegroundColor Green }
    else { $script:ProofFailed=$true; Write-Host "PROOF ERR  $Message" -ForegroundColor Red }
}

Write-Host "Kiem tra PQG Workspace" -ForegroundColor Cyan
if (Test-Path -LiteralPath $PythonExe -PathType Leaf) { Write-Host "OK  backend\.venv ton tai" -ForegroundColor Green } else { Write-Host "ERR thieu backend\.venv" -ForegroundColor Red }
if (Test-Path -LiteralPath (Join-Path $FrontendDir "node_modules") -PathType Container) { Write-Host "OK  frontend\node_modules ton tai" -ForegroundColor Green } else { Write-Host "ERR thieu frontend\node_modules" -ForegroundColor Red }
if (Test-Path -LiteralPath $BackendEnv -PathType Leaf) { Write-Host "OK  backend\.env ton tai" -ForegroundColor Green } else { Write-Host "WARN chua co backend\.env" -ForegroundColor Yellow }

$state=$null
try { $state=Read-PqgDevState -StatePath $StatePath } catch { Write-Proof $false $_.Exception.Message }
$currentSha=$null
try { $currentSha=Get-PqgCurrentSourceSha -RepositoryRoot $Root; Write-Host "INFO source SHA hien tai: $currentSha" } catch { Write-Proof $false $_.Exception.Message }
$effectiveDbPath=$null
if (Test-Path -LiteralPath $PythonExe -PathType Leaf) {
    try { $effectiveDbPath=Get-PqgConfiguredDbPath -BackendDirectory $BackendDir -PythonExecutable $PythonExe } catch { Write-Proof $false $_.Exception.Message }
} else { Write-Proof $false 'Khong co backend Python de resolve configured DB path.' }

$headerProof=$null
if ($null -eq $state) { Write-Proof $false "$StatePath khong ton tai; HTTP health khong the thay the process provenance." }
elseif ($null -ne $currentSha) { $headerProof=Test-PqgStateHeader -State $state -RepositoryRoot $Root -CurrentSourceSha $currentSha -RequireCurrentSource; Write-Proof ($headerProof.status -eq 'Match') "repository/source: $($headerProof.reason)" }
else { Write-Proof $false 'Khong co current source SHA de doi chieu dev-state.' }

if ($null -ne $state -and $null -ne $headerProof -and $headerProof.status -eq 'Match' -and $null -ne $currentSha) {
    try {
        $recordedBackendPort=[int]$state.backend.port
        $recordedFrontendPort=[int]$state.frontend.port
        if ($BackendPort -le 0) { $BackendPort=$recordedBackendPort }
        if ($FrontendPort -le 0) { $FrontendPort=$recordedFrontendPort }
    } catch { Write-Proof $false 'Recorded backend/frontend port khong hop le.' }

    $powerShellExe=$null
    try { $powerShellExe=Get-PqgPowerShellExecutable } catch { Write-Proof $false $_.Exception.Message }
    if (-not (Test-PqgHasProperty $state.backend 'reload') -or $state.backend.reload -isnot [bool]) {
        Write-Proof $false 'backend.reload bi thieu/khong hop le; khong the recompute command binding.'
    } elseif ($null -ne $powerShellExe -and $BackendPort -gt 0 -and $FrontendPort -gt 0) {
        $backendMarker=Get-PqgIdentityMarker -Role backend -RepositoryRoot $Root -SourceSha $currentSha
        $frontendMarker=Get-PqgIdentityMarker -Role frontend -RepositoryRoot $Root -SourceSha $currentSha
        $backendCommand=Get-PqgBackendCommandIdentity -RepositoryRoot $Root -SourceSha $currentSha -BackendDirectory $BackendDir -Port $recordedBackendPort -DbPath $effectiveDbPath -Reload ([bool]$state.backend.reload)
        $frontendCommand=Get-PqgFrontendCommandIdentity -RepositoryRoot $Root -SourceSha $currentSha -FrontendDirectory $FrontendDir -Port $recordedFrontendPort -BackendPort $recordedBackendPort

        $backendProof=Test-PqgProcessRecord -Record $state.backend -Role backend -ExpectedWorkingDirectory $BackendDir -ExpectedCommand $backendCommand -ExpectedIdentityMarker $backendMarker -ExpectedExecutable $powerShellExe -ExpectedPort $BackendPort -ExpectedDbPath $effectiveDbPath -RequireDbPath
        Write-Proof ($backendProof.status -eq 'Match') "backend process: $($backendProof.reason)"
        if ($backendProof.status -eq 'Match') {
            Write-Proof (Test-PqgPortOwnedByProcessTree -Port $recordedBackendPort -RootProcessId ([int]$state.backend.pid)) "backend port $recordedBackendPort thuoc recorded process tree"
            Write-Proof (Test-PqgPathEqual ([string]$state.backend.dbPath) $effectiveDbPath) "backend DB binding: $effectiveDbPath"
        }

        $frontendProof=Test-PqgProcessRecord -Record $state.frontend -Role frontend -ExpectedWorkingDirectory $FrontendDir -ExpectedCommand $frontendCommand -ExpectedIdentityMarker $frontendMarker -ExpectedExecutable $powerShellExe -ExpectedPort $FrontendPort
        Write-Proof ($frontendProof.status -eq 'Match') "frontend process: $($frontendProof.reason)"
        if ($frontendProof.status -eq 'Match') { Write-Proof (Test-PqgPortOwnedByProcessTree -Port $recordedFrontendPort -RootProcessId ([int]$state.frontend.pid)) "frontend port $recordedFrontendPort thuoc recorded process tree" }
    }
}

if ($BackendPort -le 0) { $BackendPort=8000 }
if ($FrontendPort -le 0) { $FrontendPort=5173 }
$backendUrl="http://127.0.0.1:$BackendPort"
$frontendUrl="http://localhost:$FrontendPort"

Write-Host ""
Write-Host "HTTP/runtime health (khong phai identity proof):" -ForegroundColor Cyan
if (Test-HttpOk "$backendUrl/health") {
    Write-Host "HEALTH OK   backend phan hoi: $backendUrl" -ForegroundColor Green
    try {
        $runtime=Invoke-RestMethod "$backendUrl/api/runtime/status" -TimeoutSec 5
        Write-Host "HEALTH OK   DB status: $($runtime.db.status)" -ForegroundColor Green
        Write-Host "HEALTH INFO assistant compatibility status: $($runtime.hermes.status)"
        Write-Host "HEALTH INFO n8n configured: $($runtime.n8n.configured)"
    } catch { Write-Host "HEALTH WARN backend chay nhung runtime status khong doc duoc" -ForegroundColor Yellow }
} else { Write-Host "HEALTH ERR  backend chua phan hoi tai $backendUrl" -ForegroundColor Red }
if (Test-HttpOk $frontendUrl) { Write-Host "HEALTH OK   frontend phan hoi: $frontendUrl" -ForegroundColor Green } else { Write-Host "HEALTH ERR  frontend chua phan hoi tai $frontendUrl" -ForegroundColor Red }

Write-Host ""
Write-Host "Mo app: $frontendUrl"
if ($ProofFailed) { Write-Host 'Identity proof KHONG DAT. Khong duoc dung HTTP health de suy dien dung repo/process/DB.' -ForegroundColor Red; exit 1 }
Write-Host 'Identity proof DAT; HTTP health duoc bao cao rieng.' -ForegroundColor Green
