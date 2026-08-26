$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
. (Join-Path $Root "scripts\dev-provenance.ps1")

$StatePath = Join-Path $Root ".dev\dev-state.json"
$BackendDir = Get-PqgCanonicalPath (Join-Path $Root "backend")
$FrontendDir = Get-PqgCanonicalPath (Join-Path $Root "frontend")

function Stop-ProvenProcessTree {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$RootPid,
        [Parameter(Mandatory = $true)][int]$Port
    )

    if ($RootPid -le 0) {
        throw "$Name recorded PID is invalid."
    }
    Write-Host "Dang tat process tree ${Name} da duoc chung minh (PID $RootPid)..."
    & taskkill.exe /PID $RootPid /T /F 2>$null | Out-Null

    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if ($null -eq (Get-PqgProcessSnapshot -Pid $RootPid)) { break }
        Start-Sleep -Milliseconds 100
    }
    if ($null -ne (Get-PqgProcessSnapshot -Pid $RootPid)) {
        throw "$Name PID $RootPid van dang chay sau stop attempt."
    }
    if (Test-PqgPortOwnedByProcessTree -Port $Port -RootPid $RootPid) {
        throw "$Name recorded process tree van so huu port $Port sau stop attempt."
    }
}

if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
    Write-Host "Khong thay .dev\dev-state.json. Khong co process nao duoc phep kill theo provenance." -ForegroundColor Yellow
    Write-Host "Neu ban da mo server thu cong, hay tat terminal tuong ung."
    exit 0
}

try {
    $state = Read-PqgDevState -StatePath $StatePath
} catch {
    Write-Host "TU CHOI STOP: $($_.Exception.Message). State duoc giu nguyen." -ForegroundColor Red
    exit 1
}

$headerProof = Test-PqgStateHeader -State $state -RepositoryRoot $Root
if ($headerProof.status -ne 'Match') {
    Write-Host "TU CHOI STOP: $($headerProof.reason). Khong kill PID va khong xoa state." -ForegroundColor Red
    exit 1
}

$backendProof = Test-PqgProcessRecord `
    -Record $state.backend `
    -Role backend `
    -ExpectedWorkingDirectory $BackendDir `
    -RequireDbPath
$frontendProof = Test-PqgProcessRecord `
    -Record $state.frontend `
    -Role frontend `
    -ExpectedWorkingDirectory $FrontendDir

$refusals = @()
if ($backendProof.status -in @('Mismatch', 'Incomplete')) {
    $refusals += "backend: $($backendProof.reason)"
}
if ($frontendProof.status -in @('Mismatch', 'Incomplete')) {
    $refusals += "frontend: $($frontendProof.reason)"
}
if ($refusals) {
    Write-Host 'TU CHOI STOP: process identity khong duoc chung minh. Khong process nao bi kill; state duoc giu nguyen.' -ForegroundColor Red
    foreach ($reason in $refusals) { Write-Host " - $reason" -ForegroundColor Red }
    exit 1
}

try {
    if ($frontendProof.status -eq 'Match') {
        Stop-ProvenProcessTree -Name frontend -RootPid ([int]$state.frontend.pid) -Port ([int]$state.frontend.port)
    } else {
        Write-Host "Frontend recorded PID khong con chay; khong kill process khac."
    }

    if ($backendProof.status -eq 'Match') {
        Stop-ProvenProcessTree -Name backend -RootPid ([int]$state.backend.pid) -Port ([int]$state.backend.port)
    } else {
        Write-Host "Backend recorded PID khong con chay; khong kill process khac."
    }
} catch {
    Write-Host "STOP KHONG HOAN TAT: $($_.Exception.Message). State duoc giu de dieu tra/retry." -ForegroundColor Red
    exit 1
}

Remove-Item -LiteralPath $StatePath -Force -ErrorAction Stop
Write-Host "Da stop an toan cac recorded process va xoa dev-state." -ForegroundColor Green
