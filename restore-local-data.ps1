param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,
    [string]$TargetPath,
    [switch]$WhatIf,
    [switch]$ConfirmRestore
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
. (Join-Path $root 'scripts\dev-provenance.ps1')

$backendDir = Get-PqgCanonicalPath (Join-Path $root 'backend')
$frontendDir = Get-PqgCanonicalPath (Join-Path $root 'frontend')
$python = Get-PqgCanonicalPath (Join-Path $backendDir '.venv\Scripts\python.exe')
$statePath = Join-Path $root '.dev\dev-state.json'
$defaultTarget = Get-PqgCanonicalPath (Join-Path $backendDir 'app.db')
$targetInput = if ($TargetPath) { $TargetPath } else { $defaultTarget }
$target = Get-PqgCanonicalPath $targetInput
$backup = (Resolve-Path -LiteralPath $BackupPath).Path
$manifest = "$backup.manifest.json"

if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) {
    throw 'Backup path must point to a backup database file.'
}
if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
    throw 'Backup manifest is required for restore verification.'
}
if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
    throw 'Restore target must be an existing database file.'
}
if (-not $WhatIf -and -not $ConfirmRestore) {
    throw 'Run with -WhatIf first, then use -ConfirmRestore only after the target DB is offline.'
}
if ($WhatIf -and $ConfirmRestore) {
    throw 'Use either -WhatIf or -ConfirmRestore, not both.'
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Backend Python environment is required to validate the backup.'
}

$validation = @"
import hashlib, json, pathlib, sqlite3, sys
backup = pathlib.Path(sys.argv[1])
manifest = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8'))
expected_name = sys.argv[3]
if manifest.get('format_version') != 1 or manifest.get('backup_name') != expected_name:
    raise SystemExit('manifest metadata mismatch')
if manifest.get('coverage') != 'database_only':
    raise SystemExit('unsupported backup coverage')
if manifest.get('size_bytes') != backup.stat().st_size:
    raise SystemExit('backup size mismatch')
digest = hashlib.sha256()
with backup.open('rb') as source:
    for chunk in iter(lambda: source.read(1024 * 1024), b''):
        digest.update(chunk)
if digest.hexdigest() != manifest.get('sha256'):
    raise SystemExit('backup hash mismatch')
db = sqlite3.connect(str(backup))
try:
    result = db.execute('PRAGMA integrity_check').fetchone()[0]
    print(result)
finally:
    db.close()
"@
$integrity = $validation | & $python - $backup $manifest ([System.IO.Path]::GetFileName($backup))
if ($LASTEXITCODE -ne 0 -or $integrity -ne 'ok') {
    throw 'Backup manifest/hash/integrity validation failed; no data was changed.'
}

function Assert-TargetDbOffline {
    $state = $null
    $backendProof = $null
    $frontendProof = $null
    $stateDbMatchesTarget = $false
    $knownDifferentBackendRootPid = 0

    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        try {
            $state = Read-PqgDevState -StatePath $statePath
        } catch {
            throw "Cannot prove target DB offline because dev-state is invalid: $($_.Exception.Message)"
        }

        $headerProof = Test-PqgStateHeader -State $state -RepositoryRoot $root
        if ($headerProof.status -ne 'Match') {
            throw "Cannot prove target DB offline from dev-state: $($headerProof.reason)"
        }

        $backendProof = Test-PqgProcessRecord `
            -Record $state.backend `
            -Role backend `
            -ExpectedWorkingDirectory $backendDir `
            -RequireDbPath
        $frontendProof = Test-PqgProcessRecord `
            -Record $state.frontend `
            -Role frontend `
            -ExpectedWorkingDirectory $frontendDir

        if ($backendProof.status -in @('Mismatch', 'Incomplete')) {
            throw "Cannot prove target DB offline because backend provenance is uncertain: $($backendProof.reason)"
        }
        if ($frontendProof.status -in @('Mismatch', 'Incomplete')) {
            throw "Cannot perform destructive restore with incomplete dev-state: $($frontendProof.reason)"
        }

        $stateDbMatchesTarget = Test-PqgPathEqual ([string]$state.backend.dbPath) $target
        if ($stateDbMatchesTarget) {
            if ($backendProof.status -eq 'Match') {
                throw "Restore blocked: recorded backend PID $($state.backend.pid) is running and is bound to target DB $target."
            }
            $recordedPort = ConvertTo-PqgInt $state.backend.port
            if ($null -eq $recordedPort -or $recordedPort -le 0) {
                throw 'Cannot prove target DB offline because recorded backend port is invalid.'
            }
            if (Test-PqgPortListener -Port $recordedPort) {
                throw "Restore blocked: recorded dynamic backend port $recordedPort is still listening while target DB matches dev-state."
            }
        } elseif ($backendProof.status -eq 'Match') {
            $knownDifferentBackendRootPid = [int]$state.backend.pid
        }
    }

    $listeners = @(Get-PqgLikelyBackendListeners -RepositoryRoot $root -PythonExecutable $python)
    foreach ($listener in $listeners) {
        if ($knownDifferentBackendRootPid -gt 0 -and
            (Test-PqgProcessDescendant -ChildPid ([int]$listener.pid) -AncestorPid $knownDifferentBackendRootPid)) {
            continue
        }
        throw "Cannot prove target DB offline: untracked PQG uvicorn listener found at PID $($listener.pid), port $($listener.port)."
    }

    if (-not (Test-PqgExclusiveFileAccess -Path $target)) {
        throw 'Cannot obtain exclusive access to target DB. Refusing offline restore.'
    }
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$safety = "$target.pre-restore-$stamp"
$stage = "$target.restore-stage"
$previous = "$target.previous"

if ($WhatIf) {
    Write-Host "Validated backup: $backup"
    Write-Host "Would require provenance/process/listener/exclusive-file proof that target DB is offline: $target"
    Write-Host "Would create safety backup: $safety"
    Write-Host "Would stage and atomically replace: $target"
    Write-Host 'This DB-only tool does not restore workspace files, .env, OAuth or Credential Manager data.'
    exit 0
}

Assert-TargetDbOffline

if (Test-Path -LiteralPath $previous) {
    throw 'A previous restore marker already exists. Resolve it before retrying; target was not mutated.'
}
if (Test-Path -LiteralPath $stage) {
    throw 'A restore stage already exists. Resolve it before retrying; target was not mutated.'
}

Copy-Item -LiteralPath $target -Destination $safety -ErrorAction Stop
Copy-Item -LiteralPath $backup -Destination $stage -ErrorAction Stop
try {
    Move-Item -LiteralPath $target -Destination $previous -ErrorAction Stop
    Move-Item -LiteralPath $stage -Destination $target -ErrorAction Stop
    $postIntegrity = $validation | & $python - $target $manifest ([System.IO.Path]::GetFileName($backup))
    if ($LASTEXITCODE -ne 0 -or $postIntegrity -ne 'ok') {
        throw 'Post-restore integrity check failed.'
    }
    Remove-Item -LiteralPath $previous -Force -ErrorAction Stop
} catch {
    if (Test-Path -LiteralPath $previous) {
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue
        }
        Move-Item -LiteralPath $previous -Destination $target -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Force -ErrorAction SilentlyContinue
    }
    throw
}

Write-Host "Restore complete. Safety backup retained at: $safety"
Write-Host 'Start the backend and run check-dev.ps1 for separate provenance and health checks.'
