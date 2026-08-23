[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$EvidenceRoot,
    [switch]$PreserveTerminalStatus
)

# Stops only the backend/frontend PIDs and start times recorded by the paired
# native Package D starter. It never searches for, or terminates, other processes.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$evidenceBase = [System.IO.Path]::GetFullPath((Join-Path $repo 'output\playwright'))
$EvidenceRoot = [System.IO.Path]::GetFullPath($EvidenceRoot)
$evidencePrefix = $evidenceBase.TrimEnd('\') + '\'
if (-not $EvidenceRoot.StartsWith($evidencePrefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'EvidenceRoot must be beneath output/playwright.' }
if (-not (Split-Path -Leaf $EvidenceRoot).StartsWith('package-d-native-', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'EvidenceRoot leaf must start with package-d-native-.' }
$metadataPath = Join-Path $EvidenceRoot 'run-metadata.json'
if (-not (Test-Path -LiteralPath $metadataPath)) { throw "Native Package D metadata is missing: $metadataPath" }
$metadata = Get-Content -Raw -Encoding utf8 -LiteralPath $metadataPath | ConvertFrom-Json
if ($metadata.package -ne 'D' -or $metadata.support_route -ne 'native-browser-computer-use') { throw 'Metadata is not from the Package D native support starter.' }

$results = @()
function Stop-VerifiedProcess([string]$Name, [int]$ProcessId, [string]$RecordedStart, [string]$ExpectedCommandFragment, [string]$Kind) {
    try {
        $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if (-not $process) { return @{ name=$Name; pid=$ProcessId; kind=$Kind; result='ALREADY_EXITED' } }
        $recorded = [datetimeoffset]::Parse($RecordedStart)
        $actual = [datetimeoffset]$process.StartTime
        if ([math]::Abs(($actual.UtcDateTime - $recorded.UtcDateTime).TotalSeconds) -gt 1) { return @{ name=$Name; pid=$ProcessId; kind=$Kind; result='PID_REUSED_NOT_STOPPED' } }
        if ($ExpectedCommandFragment) {
            $commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop).CommandLine
            if ($commandLine -notlike "*$ExpectedCommandFragment*") { return @{ name=$Name; pid=$ProcessId; kind=$Kind; result='COMMAND_MISMATCH_NOT_STOPPED' } }
        }
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        $deadline = (Get-Date).AddSeconds(5)
        do { Start-Sleep -Milliseconds 100; $remaining = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue } while ($remaining -and (Get-Date) -lt $deadline)
        if ($remaining) { return @{ name=$Name; pid=$ProcessId; kind=$Kind; result='STOP_FAILED'; message='Process did not exit within 5 seconds.' } }
        return @{ name=$Name; pid=$ProcessId; kind=$Kind; result='STOPPED' }
    } catch { return @{ name=$Name; pid=$ProcessId; kind=$Kind; result='STOP_FAILED'; message=$_.Exception.Message } }
}
foreach ($name in @('frontend', 'backend')) {
    $entry = $metadata.launch.$name
    if (-not $entry -or -not $entry.pid -or -not $entry.start_time) {
        $results += @{ name=$name; result='NOT_RECORDED' }
        continue
    }
    try {
        $process = Get-Process -Id ([int]$entry.pid) -ErrorAction SilentlyContinue
        if (-not $process) {
            $entry.exited = $true
            $results += @{ name=$name; pid=$entry.pid; result='ALREADY_EXITED' }
            continue
        }
        $recordedStart = [datetimeoffset]::Parse([string]$entry.start_time)
        $actualStart = [datetimeoffset]$process.StartTime
        if ($actualStart.UtcDateTime -ne $recordedStart.UtcDateTime) {
            $results += @{ name=$name; pid=$entry.pid; result='PID_REUSED_NOT_STOPPED' }
            continue
        }
        Stop-Process -Id $process.Id -Force -ErrorAction Stop
        $deadline = (Get-Date).AddSeconds(5)
        do {
            Start-Sleep -Milliseconds 100
            $remaining = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
        } while ($remaining -and (Get-Date) -lt $deadline)
        if ($remaining) {
            $results += @{ name=$name; pid=$entry.pid; result='STOP_FAILED'; message='Process did not exit within 5 seconds.' }
            continue
        }
        $entry.exited = $true
        $results += @{ name=$name; pid=$entry.pid; result='STOPPED' }
    } catch {
        $results += @{ name=$name; pid=$entry.pid; result='STOP_FAILED'; message=$_.Exception.Message }
    }
}

# Python virtual-environment launchers can hand off to a child process. The
# listener identity is captured by the starter and requires both its start
# time and Package D command fragment before this script may stop it.
foreach ($name in @('frontend', 'backend')) {
    $entry = $metadata.launch.$name
    if (-not $entry -or -not $entry.listener_pid -or -not $entry.listener_start_time -or -not $entry.listener_command_fragment) {
        $results += @{ name=$name; kind='listener'; result='LISTENER_NOT_RECORDED' }
        continue
    }
    $results += Stop-VerifiedProcess $name ([int]$entry.listener_pid) ([string]$entry.listener_start_time) ([string]$entry.listener_command_fragment) 'listener'
}

foreach ($result in @($results | Where-Object { $_.result -eq 'PID_REUSED_NOT_STOPPED' -and -not $_.kind })) {
    $result.result = 'LAUNCHER_PID_REUSED'
}

foreach ($name in @('frontend', 'backend')) {
    $port = [int]$metadata.ports.$name
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        $results += @{ name=$name; port=$port; result='PORT_STILL_LISTENING' }
    }
}

$cleanupIncomplete = @($results | Where-Object { $_.result -in @('PID_REUSED_NOT_STOPPED', 'COMMAND_MISMATCH_NOT_STOPPED', 'STOP_FAILED', 'PORT_STILL_LISTENING', 'LISTENER_NOT_RECORDED') }).Count -gt 0
if ($cleanupIncomplete) {
    $metadata.status = 'CLEANUP_INCOMPLETE'
} elseif (-not ($PreserveTerminalStatus -and $metadata.status -in @('PASS', 'FAIL'))) {
    $metadata.status = 'CLEANED_NOT_RUN'
}
$metadata.completed_at = (Get-Date).ToString('o')
$metadata.cleanup = @{ at=$metadata.completed_at; processes=$results }
$metadata | ConvertTo-Json -Depth 16 | Set-Content -Encoding utf8 -LiteralPath $metadataPath
if ($cleanupIncomplete) { throw 'One or more recorded Package D native processes could not be confirmed stopped; terminal metadata was written.' }
exit 0
