param(
    [int]$BackendPort = 0,
    [string]$WorkspacePath = "",
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StatePath = Join-Path $Root ".dev\dev-state.json"

if ((Test-Path $StatePath) -and $BackendPort -eq 0) {
    $state = Get-Content $StatePath -Raw | ConvertFrom-Json
    $BackendPort = [int]$state.backendPort
}

if ($BackendPort -eq 0) {
    $BackendPort = 8000
}

if (-not $WorkspacePath) {
    $WorkspacePath = $Root
}

$BackendUrl = "http://127.0.0.1:$BackendPort"

function Assert-Ok {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

Write-Host "Smoke test DIRAP Local Workbench" -ForegroundColor Cyan
Write-Host "Backend: $BackendUrl"
Write-Host "Workspace: $WorkspacePath"

$health = Invoke-RestMethod "$BackendUrl/health" -TimeoutSec 10
Assert-Ok ($health.status -eq "ok") "Backend health failed"
Write-Host "OK  health"

$runtime = Invoke-RestMethod "$BackendUrl/api/runtime/status" -TimeoutSec 10
Assert-Ok ($runtime.backend -eq "ok") "Runtime status failed"
Assert-Ok ($runtime.db.status -eq "ok") "DB status failed"
Write-Host "OK  runtime: Hermes=$($runtime.hermes.status), n8n=$($runtime.n8n.configured)"

$sessionBody = @{
    title = "Smoke Test $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    workspace_path = $WorkspacePath
} | ConvertTo-Json

$session = Invoke-RestMethod "$BackendUrl/api/sessions" -Method Post -ContentType "application/json" -Body $sessionBody -TimeoutSec 10
Assert-Ok ($null -ne $session.id) "Session creation failed"
Write-Host "OK  session: $($session.id)"

$promptBody = @{
    prompt = "Tra loi dung mot tu: OK"
} | ConvertTo-Json

$task = Invoke-RestMethod "$BackendUrl/api/sessions/$($session.id)/prompt" -Method Post -ContentType "application/json" -Body $promptBody -TimeoutSec 10
Assert-Ok ($null -ne $task.id) "Prompt submit failed"
Write-Host "OK  prompt queued: $($task.id)"

$eventUrl = "$BackendUrl/api/sessions/$($session.id)/events"
$request = [System.Net.HttpWebRequest]::Create($eventUrl)
$request.Method = "GET"
$request.Timeout = $TimeoutSeconds * 1000
$request.ReadWriteTimeout = $TimeoutSeconds * 1000
$response = $request.GetResponse()
$stream = $response.GetResponseStream()
$reader = New-Object System.IO.StreamReader($stream)

$events = New-Object System.Collections.Generic.List[string]
$payloadText = ""
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

try {
    while ((Get-Date) -lt $deadline) {
        $line = $reader.ReadLine()
        if ($null -eq $line) {
            Start-Sleep -Milliseconds 100
            continue
        }
        if ($line.StartsWith("event: ")) {
            $name = $line.Substring(7)
            $events.Add($name)
            if ($name -eq "done") {
                break
            }
        } elseif ($line.StartsWith("data: ")) {
            $payloadText += $line.Substring(6)
        }
    }
} finally {
    $reader.Dispose()
    $response.Dispose()
}

Assert-Ok ($events.Contains("done")) "SSE did not emit done"
Assert-Ok (($events.Contains("token")) -or ($events.Contains("error"))) "SSE emitted neither token nor error"

if ($events.Contains("error")) {
    Write-Host "WARN SSE emitted error. Payload:"
    Write-Host $payloadText
} else {
    Write-Host "OK  SSE token stream completed"
}

Write-Host "OK  smoke test completed"
