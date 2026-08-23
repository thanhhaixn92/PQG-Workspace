[CmdletBinding()]
param([Parameter(Mandatory)][string]$EvidenceRoot,[switch]$PreserveTerminalStatus)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$base = [IO.Path]::GetFullPath((Join-Path $repo 'output\playwright'))
$EvidenceRoot = [IO.Path]::GetFullPath($EvidenceRoot)
if (-not $EvidenceRoot.StartsWith($base.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'EvidenceRoot must be beneath output/playwright.' }
$path = Join-Path $EvidenceRoot 'run-metadata.json'
if (-not (Test-Path -LiteralPath $path)) { throw 'Package F metadata is missing.' }
$metadata = Get-Content -Raw -Encoding utf8 -LiteralPath $path | ConvertFrom-Json
if ($metadata.package -ne 'F' -or $metadata.support_route -ne 'native-browser-computer-use') { throw 'Metadata is not Package F native fidelity support.' }

$results = @()
function Test-LoopbackPortOpen([int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $pending = $client.BeginConnect([System.Net.IPAddress]::Loopback, $Port, $null, $null)
        if (-not $pending.AsyncWaitHandle.WaitOne(1000)) { return $false }
        $client.EndConnect($pending)
        return $true
    } catch { return $false }
    finally { $client.Dispose() }
}
function Stop-RecordedProcess([string]$Name, [string]$Kind, $Entry, [bool]$Required) {
    if (-not $Entry -or -not $Entry.pid -or -not $Entry.start_time) {
        if ($Required) { return @{name=$Name;kind=$Kind;result='IDENTITY_MISMATCH_NOT_STOPPED';message='Recorded PID/start time is missing.'} }
        return @{name=$Name;kind=$Kind;result='ALREADY_EXITED'}
    }
    $process = Get-Process -Id ([int]$Entry.pid) -ErrorAction SilentlyContinue
    if (-not $process) { return @{name=$Name;kind=$Kind;pid=$Entry.pid;result='ALREADY_EXITED'} }
    $difference = [math]::Abs((([datetimeoffset]$process.StartTime).UtcDateTime - ([datetimeoffset]::Parse([string]$Entry.start_time)).UtcDateTime).TotalSeconds)
    if ($difference -gt 1) { return @{name=$Name;kind=$Kind;pid=$Entry.pid;result='IDENTITY_MISMATCH_NOT_STOPPED';message='PID start time differs from recorded identity.'} }
    try {
        Stop-Process -Id $process.Id -Force -ErrorAction Stop
        $deadline = (Get-Date).AddSeconds(5)
        do { Start-Sleep -Milliseconds 100; $remaining = Get-Process -Id $process.Id -ErrorAction SilentlyContinue } while ($remaining -and (Get-Date) -lt $deadline)
        if ($remaining) { return @{name=$Name;kind=$Kind;pid=$Entry.pid;result='STOP_FAILED'} }
        return @{name=$Name;kind=$Kind;pid=$Entry.pid;result='STOPPED'}
    } catch { return @{name=$Name;kind=$Kind;pid=$Entry.pid;result='STOP_FAILED';message=$_.Exception.Message} }
}
foreach ($name in @('frontend','backend')) {
    $entry = $metadata.launch.$name
    if (-not $entry -or -not $entry.listener_pid -or -not $entry.listener_start_time -or -not $entry.listener_identity_run_id -or $entry.listener_identity_run_id -ne $metadata.run_id) {
        $results += @{name=$name;kind='listener';result='IDENTITY_MISMATCH_NOT_STOPPED';message='Listener identity was not bound to this run.'}
        continue
    }
    $listener = @{pid=$entry.listener_pid;start_time=$entry.listener_start_time}
    $results += Stop-RecordedProcess $name 'listener' $listener $true
}
foreach ($name in @('frontend','backend')) { $results += Stop-RecordedProcess $name 'launcher' $metadata.launch.$name $true }
foreach ($name in @('frontend','backend')) {
    $port = [int]$metadata.ports.$name
    if (Test-LoopbackPortOpen $port) { $results += @{name=$name;kind='port';port=$port;result='PORT_STILL_OPEN'} }
    else { $results += @{name=$name;kind='port';port=$port;result='PORT_CLOSED'} }
}
$bad = @($results | Where-Object { $_.result -in @('IDENTITY_MISMATCH_NOT_STOPPED','STOP_FAILED','PORT_STILL_OPEN') }).Count -gt 0
if ($bad) { $metadata.status='CLEANUP_INCOMPLETE' }
elseif (-not ($PreserveTerminalStatus -and $metadata.status -in @('PASS','PARTIAL','FAIL','G_SYNTHETIC_EVALUATOR_PASS'))) { $metadata.status='CLEANED_NOT_RUN' }
$metadata.completed_at=(Get-Date).ToString('o')
$metadata.cleanup=@{at=$metadata.completed_at;processes=$results}
$metadata | ConvertTo-Json -Depth 16 | Set-Content -Encoding utf8 -LiteralPath $path
if ($bad) { throw 'Package F cleanup could not confirm all recorded processes stopped.' }
exit 0
