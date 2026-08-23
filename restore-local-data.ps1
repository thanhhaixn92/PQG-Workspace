param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,
    [string]$TargetPath,
    [switch]$WhatIf,
    [switch]$ConfirmRestore
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$defaultTarget = [System.IO.Path]::GetFullPath((Join-Path $root 'backend\app.db'))
$targetInput = if ($TargetPath) { $TargetPath } else { $defaultTarget }
$target = [System.IO.Path]::GetFullPath($targetInput)
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
    throw 'Run with -WhatIf first, then use -ConfirmRestore only after stopping backend, Hermes, outbox and MCP.'
}
if ($WhatIf -and $ConfirmRestore) {
    throw 'Use either -WhatIf or -ConfirmRestore, not both.'
}

if ($ConfirmRestore -and $target -eq $defaultTarget) {
    $busyPorts = @(8000, 8100) | Where-Object {
        Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue
    }
    if ($busyPorts) {
        throw 'A local backend appears to be running. Stop it before an offline restore.'
    }
}

$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
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
if ($integrity -ne 'ok') {
    throw 'Backup integrity check failed; no data was changed.'
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$safety = "$target.pre-restore-$stamp"
$stage = "$target.restore-stage"
$previous = "$target.previous"

if ($WhatIf) {
    Write-Host "Validated backup: $backup"
    Write-Host "Would create safety backup: $safety"
    Write-Host "Would stage and atomically replace: $target"
    Write-Host 'This DB-only tool does not restore workspace files, .env, OAuth or Credential Manager data.'
    exit 0
}

Copy-Item -LiteralPath $target -Destination $safety -ErrorAction Stop
Copy-Item -LiteralPath $backup -Destination $stage -ErrorAction Stop
if (Test-Path -LiteralPath $previous) {
    throw 'A previous restore marker already exists. Resolve it before retrying.'
}
try {
    Move-Item -LiteralPath $target -Destination $previous -ErrorAction Stop
    Move-Item -LiteralPath $stage -Destination $target -ErrorAction Stop
    $postIntegrity = $validation | & $python - $target $manifest ([System.IO.Path]::GetFileName($backup))
    if ($postIntegrity -ne 'ok') {
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
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Force -ErrorAction SilentlyContinue }
    throw
}

Write-Host "Restore complete. Safety backup retained at: $safety"
Write-Host 'Start the backend and run check-dev.ps1 for the post-restore health check.'
