param(
    [string]$BackendUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $Root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Missing backend\.venv."
}

try {
    $backup = Invoke-RestMethod -Method Post -Uri "$BackendUrl/api/local-data/backup" -TimeoutSec 30
} catch {
    throw "Cannot create a backup. Check backend at $BackendUrl first."
}

$backupPath = [string]$backup.backup_path
if (-not (Test-Path -LiteralPath $backupPath)) {
    throw "Backend reported a successful backup but the file was not found."
}

$drill = @'
import os, sqlite3, sys, tempfile
from pathlib import Path

backup_path = Path(sys.argv[1])
fd, restore_name = tempfile.mkstemp(prefix="dirap-memory-hub-restore-drill-", suffix=".db")
os.close(fd)
Path(restore_name).unlink(missing_ok=True)
try:
    source = sqlite3.connect(backup_path)
    restored = sqlite3.connect(restore_name)
    try:
        source.backup(restored)
        integrity = restored.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"integrity_check={integrity}")
        records = restored.execute("SELECT COUNT(*) FROM memory_hub_records").fetchone()[0]
        print(f"RESTORE_DRILL_PASS memory_hub_records={records}")
    finally:
        restored.close()
        source.close()
finally:
    Path(restore_name).unlink(missing_ok=True)
'@ | & $PythonExe - $backupPath

if ($LASTEXITCODE -ne 0) {
    throw "Restore drill failed; the original backup remains at $backupPath."
}

Write-Host "OK  $drill" -ForegroundColor Green
Write-Host "Original backup retained at: $backupPath" -ForegroundColor Green
