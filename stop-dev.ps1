$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StatePath = Join-Path $Root ".dev\dev-state.json"

function Get-ChildProcessIds {
    param([int]$ParentPid)

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentPid" -ErrorAction SilentlyContinue
    $ids = @()
    foreach ($child in $children) {
        $ids += [int]$child.ProcessId
        $ids += Get-ChildProcessIds -ParentPid ([int]$child.ProcessId)
    }
    return $ids
}

function Stop-RecordedProcessTree {
    param(
        [string]$Name,
        [int]$RootPid
    )

    if ($RootPid -le 0) {
        Write-Host "Bo qua ${Name}: script khong mo process moi cho muc nay."
        return
    }

    $process = Get-Process -Id $RootPid -ErrorAction SilentlyContinue
    if (-not $process) {
        Write-Host "$Name da dung hoac khong con ton tai."
        return
    }

    $childIds = @(Get-ChildProcessIds -ParentPid $RootPid)
    [array]::Reverse($childIds)
    foreach ($childId in $childIds) {
        $childProcess = Get-Process -Id $childId -ErrorAction SilentlyContinue
        if ($childProcess) {
            Write-Host "Dang tat process con cua ${Name} (PID $childId)..."
            Stop-Process -Id $childId -Force -ErrorAction SilentlyContinue
        }
    }

    Write-Host "Dang tat ${Name} wrapper (PID $RootPid)..."
    Stop-Process -Id $RootPid -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path $StatePath)) {
    Write-Host "Khong thay .dev\dev-state.json. Khong co process nao do start-dev.ps1 ghi lai."
    Write-Host "Neu ban da mo server thu cong, hay tat cua so terminal tuong ung."
    exit 0
}

$state = Get-Content $StatePath -Raw | ConvertFrom-Json

Stop-RecordedProcessTree -Name "frontend" -RootPid ([int]$state.frontendPid)
Stop-RecordedProcessTree -Name "backend" -RootPid ([int]$state.backendPid)

Remove-Item $StatePath -Force
Write-Host "Da hoan tat stop-dev.ps1."
