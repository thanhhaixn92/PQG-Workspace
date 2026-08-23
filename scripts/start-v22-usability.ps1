param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^P[1-5]$')]
    [string]$Participant
)

# Starts one disposable, isolated usability environment.  It deliberately
# seeds no Work: each participant performs the same journey from a clean slate.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$number = [int]$Participant.Substring(1)
$backendPort = 8020 + $number
$frontendPort = 5200 + $number
$root = Join-Path $env:TEMP "uat-codex-usability-$Participant-$stamp"
$workspace = Join-Path $root 'workspace'
New-Item -ItemType Directory -Path $workspace -Force | Out-Null

$env:DB_PATH = Join-Path $root 'app.db'
$env:DEFAULT_WORKSPACE_ROOT = $workspace
$env:CORS_ORIGINS = "http://127.0.0.1:$frontendPort"
$env:HERMES_DEV_MOCK = '1'
$env:OUTBOX_DISPATCHER_ENABLED = '0'
$env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$backendPort"
$env:VITE_SHOW_TEST_WORKS = '0'

$backendLog = Join-Path $root 'backend.stdout.log'
$backendErrorLog = Join-Path $root 'backend.stderr.log'
$frontendLog = Join-Path $root 'frontend.stdout.log'
$frontendErrorLog = Join-Path $root 'frontend.stderr.log'
$backend = Start-Process -FilePath (Join-Path $repo 'backend\.venv\Scripts\python.exe') -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$backendPort",'--lifespan','on') -WorkingDirectory (Join-Path $repo 'backend') -WindowStyle Hidden -RedirectStandardOutput $backendLog -RedirectStandardError $backendErrorLog -PassThru
$frontend = Start-Process -FilePath 'node.exe' -ArgumentList @((Join-Path $repo 'frontend\node_modules\vite\bin\vite.js'),'--host','127.0.0.1','--port',"$frontendPort",'--strictPort') -WorkingDirectory (Join-Path $repo 'frontend') -WindowStyle Hidden -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErrorLog -PassThru

for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $health = Invoke-RestMethod "http://127.0.0.1:$backendPort/health"
        $page = Invoke-WebRequest "http://127.0.0.1:$frontendPort" -UseBasicParsing
        if ($health.status -eq 'ok' -and $page.StatusCode -eq 200) { break }
    } catch { Start-Sleep -Milliseconds 250 }
    if ($attempt -eq 59) { throw 'Usability environment did not become ready.' }
}

@{
    participant = $Participant
    launched_at = (Get-Date).ToString('o')
    url = "http://127.0.0.1:$frontendPort"
    backend_pid = $backend.Id
    frontend_pid = $frontend.Id
    data_root = $root
    data_prefix = 'uat-codex-'
    hermes_mode = 'dev_mock'
    reset = 'fresh SQLite DB and managed workspace; no prior participant data'
} | ConvertTo-Json | Set-Content -Path (Join-Path $root 'launcher-metadata.json') -Encoding utf8

Write-Output "Participant $Participant is ready at http://127.0.0.1:$frontendPort"
Write-Output "Metadata: $(Join-Path $root 'launcher-metadata.json')"
Write-Output "Stop only these processes after the session: Stop-Process -Id $($backend.Id),$($frontend.Id)"
