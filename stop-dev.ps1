$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
. (Join-Path $Root "scripts\dev-provenance.ps1")

$StatePath = Join-Path $Root ".dev\dev-state.json"
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
$BackendCommandIdentity = "uvicorn app.main:app"
$FrontendCommandIdentity = "npm run dev"

function Stop-ProvenProcessTree {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$RootProcessId
    )

    if ($RootProcessId -le 0) {
        throw "$Name recorded PID is invalid."
    }
    Write-Host "Dang tat process tree ${Name} da duoc chung minh (PID $RootProcessId)..."
    & taskkill.exe /PID $RootProcessId /T /F 2>$null | Out-Null

    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if ($null -eq (Get-PqgProcessSnapshot -ProcessId $RootProcessId)) { break }
        Start-Sleep -Milliseconds 100
    }
    if ($null -ne (Get-PqgProcessSnapshot -ProcessId $RootProcessId)) {
        throw "$Name PID $RootProcessId van dang chay sau stop attempt."
    }
}

if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
    Write-Host "Khong thay .dev\dev-state.json. Khong co process nao duoc phep kill theo provenance." -ForegroundColor Yellow
    Write-Host "Neu ban da mo server thu cong, hay tat terminal tuong ung."
    exit 0
}

try {
    $state = Read-PqgDevState -StatePath $StatePath
    $currentSha = Get-PqgCurrentSourceSha -RepositoryRoot $Root
    $powerShellExe = Get-PqgPowerShellExecutable
    $backendDbPath = Get-PqgConfiguredDbPath -BackendDirectory $BackendDir -PythonExecutable $PythonExe
} catch {
    Write-Host "TU CHOI STOP: $($_.Exception.Message). State duoc giu nguyen." -ForegroundColor Red
    exit 1
}

$headerProof = Test-PqgStateHeader -State $state -RepositoryRoot $Root -CurrentSourceSha $currentSha -RequireCurrentSource
if ($headerProof.status -ne 'Match') {
    Write-Host "TU CHOI STOP: $($headerProof.reason). Khong kill PID va khong xoa state." -ForegroundColor Red
    exit 1
}

$backendMarker = Get-PqgIdentityMarker -Role backend -RepositoryRoot $Root -SourceSha $currentSha
$frontendMarker = Get-PqgIdentityMarker -Role frontend -RepositoryRoot $Root -SourceSha $currentSha

$backendProof = Test-PqgProcessRecord `
    -Record $state.backend `
    -Role backend `
    -ExpectedWorkingDirectory $BackendDir `
    -ExpectedCommand $BackendCommandIdentity `
    -ExpectedIdentityMarker $backendMarker `
    -ExpectedExecutable $powerShellExe `
    -ExpectedDbPath $backendDbPath `
    -RequireDbPath
$frontendProof = Test-PqgProcessRecord `
    -Record $state.frontend `
    -Role frontend `
    -ExpectedWorkingDirectory $FrontendDir `
    -ExpectedCommand $FrontendCommandIdentity `
    -ExpectedIdentityMarker $frontendMarker `
    -ExpectedExecutable $powerShellExe

$refusals = @()
if ($backendProof.status -in @('Mismatch', 'Incomplete')) {
    $refusals += "backend: $($backendProof.reason)"
}
if ($frontendProof.status -in @('Mismatch', 'Incomplete')) {
    $refusals += "frontend: $($frontendProof.reason)"
}
if ($refusals.Count -gt 0) {
    Write-Host 'TU CHOI STOP: process identity khong duoc chung minh. Khong process nao bi kill; state duoc giu nguyen.' -ForegroundColor Red
    foreach ($reason in $refusals) { Write-Host " - $reason" -ForegroundColor Red }
    exit 1
}

try {
    if ($frontendProof.status -eq 'Match') {
        Stop-ProvenProcessTree -Name frontend -RootProcessId ([int]$state.frontend.pid)
    } else {
        Write-Host "Frontend recorded PID khong con chay; khong kill process khac."
    }

    if ($backendProof.status -eq 'Match') {
        Stop-ProvenProcessTree -Name backend -RootProcessId ([int]$state.backend.pid)
    } else {
        Write-Host "Backend recorded PID khong con chay; khong kill process khac."
    }
} catch {
    Write-Host "STOP KHONG HOAN TAT: $($_.Exception.Message). State duoc giu de dieu tra/retry." -ForegroundColor Red
    exit 1
}

Remove-Item -LiteralPath $StatePath -Force -ErrorAction Stop
Write-Host "Da stop an toan cac recorded process va xoa dev-state." -ForegroundColor Green
