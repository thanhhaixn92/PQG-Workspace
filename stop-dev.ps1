param(
    [string]$DevStatePath
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
. (Join-Path $Root "scripts\dev-provenance.ps1")

$StatePath = if ($DevStatePath) { [System.IO.Path]::GetFullPath($DevStatePath) } else { Join-Path $Root ".dev\dev-state.json" }
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"

function Stop-ProvenProcessTree {
    param([Parameter(Mandatory = $true)][string]$Name,[Parameter(Mandatory = $true)][int]$RootProcessId)
    if ($RootProcessId -le 0) { throw "$Name recorded PID is invalid." }
    Write-Host "Dang tat process tree ${Name} da duoc chung minh (PID $RootProcessId)..."
    & taskkill.exe /PID $RootProcessId /T /F 2>$null | Out-Null
    for ($attempt=0; $attempt -lt 20; $attempt++) {
        if ($null -eq (Get-PqgProcessSnapshot -ProcessId $RootProcessId)) { break }
        Start-Sleep -Milliseconds 100
    }
    if ($null -ne (Get-PqgProcessSnapshot -ProcessId $RootProcessId)) { throw "$Name PID $RootProcessId van dang chay sau stop attempt." }
}

if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
    Write-Host "Khong thay $StatePath. Khong co process nao duoc phep kill theo provenance." -ForegroundColor Yellow
    Write-Host "Neu ban da mo server thu cong, hay tat terminal tuong ung."
    exit 0
}

try {
    $state=Read-PqgDevState -StatePath $StatePath
    $currentSha=Get-PqgCurrentSourceSha -RepositoryRoot $Root
    $powerShellExe=Get-PqgPowerShellExecutable
    $backendDbPath=Get-PqgConfiguredDbPath -BackendDirectory $BackendDir -PythonExecutable $PythonExe
} catch {
    Write-Host "TU CHOI STOP: $($_.Exception.Message). State duoc giu nguyen." -ForegroundColor Red
    exit 1
}

$headerProof=Test-PqgStateHeader -State $state -RepositoryRoot $Root -CurrentSourceSha $currentSha -RequireCurrentSource
if ($headerProof.status -ne 'Match') { Write-Host "TU CHOI STOP: $($headerProof.reason). Khong kill PID va khong xoa state." -ForegroundColor Red; exit 1 }
if (-not (Test-PqgHasProperty $state.backend 'reload') -or $state.backend.reload -isnot [bool]) { Write-Host 'TU CHOI STOP: backend.reload bi thieu/khong hop le. Khong process nao bi kill; state duoc giu nguyen.' -ForegroundColor Red; exit 1 }

try { $backendPort=[int]$state.backend.port; $frontendPort=[int]$state.frontend.port }
catch { Write-Host 'TU CHOI STOP: recorded port khong hop le. State duoc giu nguyen.' -ForegroundColor Red; exit 1 }

$backendMarker=Get-PqgIdentityMarker -Role backend -RepositoryRoot $Root -SourceSha $currentSha
$frontendMarker=Get-PqgIdentityMarker -Role frontend -RepositoryRoot $Root -SourceSha $currentSha
$backendCommand=Get-PqgBackendCommandIdentity -RepositoryRoot $Root -SourceSha $currentSha -BackendDirectory $BackendDir -Port $backendPort -DbPath $backendDbPath -Reload ([bool]$state.backend.reload)
$frontendCommand=Get-PqgFrontendCommandIdentity -RepositoryRoot $Root -SourceSha $currentSha -FrontendDirectory $FrontendDir -Port $frontendPort -BackendPort $backendPort

$backendProof=Test-PqgProcessRecord -Record $state.backend -Role backend -ExpectedWorkingDirectory $BackendDir -ExpectedCommand $backendCommand -ExpectedIdentityMarker $backendMarker -ExpectedExecutable $powerShellExe -ExpectedPort $backendPort -ExpectedDbPath $backendDbPath -RequireDbPath
$frontendProof=Test-PqgProcessRecord -Record $state.frontend -Role frontend -ExpectedWorkingDirectory $FrontendDir -ExpectedCommand $frontendCommand -ExpectedIdentityMarker $frontendMarker -ExpectedExecutable $powerShellExe -ExpectedPort $frontendPort

$refusals=@()
if ($backendProof.status -in @('Mismatch','Incomplete')) { $refusals += "backend: $($backendProof.reason)" }
if ($frontendProof.status -in @('Mismatch','Incomplete')) { $refusals += "frontend: $($frontendProof.reason)" }
if ($refusals.Count -gt 0) {
    Write-Host 'TU CHOI STOP: process identity khong duoc chung minh. Khong process nao bi kill; state duoc giu nguyen.' -ForegroundColor Red
    foreach ($reason in $refusals) { Write-Host " - $reason" -ForegroundColor Red }
    exit 1
}

try {
    if ($frontendProof.status -eq 'Match') { Stop-ProvenProcessTree -Name frontend -RootProcessId ([int]$state.frontend.pid) } else { Write-Host 'Frontend recorded PID khong con chay; khong kill process khac.' }
    if ($backendProof.status -eq 'Match') { Stop-ProvenProcessTree -Name backend -RootProcessId ([int]$state.backend.pid) } else { Write-Host 'Backend recorded PID khong con chay; khong kill process khac.' }
} catch {
    Write-Host "STOP KHONG HOAN TAT: $($_.Exception.Message). State duoc giu de dieu tra/retry." -ForegroundColor Red
    exit 1
}

Remove-Item -LiteralPath $StatePath -Force -ErrorAction Stop
Write-Host 'Da stop an toan cac recorded process va xoa dev-state.' -ForegroundColor Green
