Set-StrictMode -Version Latest

function Get-PqgCanonicalPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw 'Path must not be empty.'
    }
    return [System.IO.Path]::GetFullPath($Path)
}

function Test-PqgPathEqual {
    param(
        [Parameter(Mandatory = $true)][string]$Left,
        [Parameter(Mandatory = $true)][string]$Right
    )

    try {
        $leftFull = Get-PqgCanonicalPath $Left
        $rightFull = Get-PqgCanonicalPath $Right
    } catch {
        return $false
    }
    return [string]::Equals($leftFull, $rightFull, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-PqgHasProperty {
    param(
        [object]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )

    return ($null -ne $Object -and $null -ne $Object.PSObject.Properties[$Name])
}

function Get-PqgCurrentSourceSha {
    param([Parameter(Mandatory = $true)][string]$RepositoryRoot)

    $sha = (& git -C $RepositoryRoot rev-parse HEAD 2>$null | Select-Object -First 1)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$sha)) {
        throw 'Cannot determine the current Git source SHA.'
    }
    $sha = ([string]$sha).Trim()
    if ($sha -notmatch '^[0-9a-fA-F]{40}$') {
        throw "Invalid Git source SHA: $sha"
    }
    return $sha.ToLowerInvariant()
}

function Read-PqgDevState {
    param([Parameter(Mandatory = $true)][string]$StatePath)

    if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
        return $null
    }
    try {
        return (Get-Content -LiteralPath $StatePath -Raw -ErrorAction Stop | ConvertFrom-Json)
    } catch {
        throw "Invalid dev-state JSON at $StatePath"
    }
}

function New-PqgProofResult {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('Match', 'NotRunning', 'Mismatch', 'Incomplete')][string]$Status,
        [Parameter(Mandatory = $true)][string]$Reason,
        [object]$Snapshot = $null
    )

    return [pscustomobject]@{
        status = $Status
        reason = $Reason
        snapshot = $Snapshot
    }
}

function Test-PqgStateHeader {
    param(
        [object]$State,
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [string]$CurrentSourceSha,
        [switch]$RequireCurrentSource
    )

    if ($null -eq $State) {
        return New-PqgProofResult -Status 'Incomplete' -Reason 'dev-state is missing'
    }
    foreach ($name in @('schemaVersion', 'repositoryRoot', 'sourceSha', 'startedAt', 'backend', 'frontend')) {
        if (-not (Test-PqgHasProperty $State $name)) {
            return New-PqgProofResult -Status 'Incomplete' -Reason "dev-state is missing $name"
        }
    }
    if ([int]$State.schemaVersion -ne 2) {
        return New-PqgProofResult -Status 'Incomplete' -Reason 'dev-state schemaVersion must be 2'
    }
    if (-not (Test-PqgPathEqual ([string]$State.repositoryRoot) $RepositoryRoot)) {
        return New-PqgProofResult -Status 'Mismatch' -Reason 'repositoryRoot does not match this checkout'
    }
    $sourceSha = ([string]$State.sourceSha).ToLowerInvariant()
    if ($sourceSha -notmatch '^[0-9a-f]{40}$') {
        return New-PqgProofResult -Status 'Incomplete' -Reason 'sourceSha is missing or invalid'
    }
    $startedAt = [DateTimeOffset]::MinValue
    if (-not [DateTimeOffset]::TryParse([string]$State.startedAt, [ref]$startedAt)) {
        return New-PqgProofResult -Status 'Incomplete' -Reason 'startedAt is missing or invalid'
    }
    if ($RequireCurrentSource) {
        if ([string]::IsNullOrWhiteSpace($CurrentSourceSha)) {
            return New-PqgProofResult -Status 'Incomplete' -Reason 'current source SHA was not supplied'
        }
        if (-not [string]::Equals($sourceSha, $CurrentSourceSha.ToLowerInvariant(), [System.StringComparison]::Ordinal)) {
            return New-PqgProofResult -Status 'Mismatch' -Reason 'sourceSha does not match the current checkout'
        }
    }
    return New-PqgProofResult -Status 'Match' -Reason 'repository/source provenance is structurally valid'
}

function Get-PqgProcessSnapshot {
    param([Parameter(Mandatory = $true)][int]$Pid)

    if ($Pid -le 0) {
        return $null
    }
    $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $Pid" -ErrorAction SilentlyContinue
    if ($null -eq $cim) {
        return $null
    }
    $process = Get-Process -Id $Pid -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return $null
    }

    $executable = [string]$cim.ExecutablePath
    if ([string]::IsNullOrWhiteSpace($executable)) {
        try { $executable = [string]$process.Path } catch { $executable = '' }
    }

    return [pscustomobject]@{
        pid = $Pid
        parentPid = [int]$cim.ParentProcessId
        processStartTime = $process.StartTime.ToUniversalTime().ToString('o')
        commandLine = [string]$cim.CommandLine
        executable = $executable
    }
}

function Test-PqgProcessRecord {
    param(
        [object]$Record,
        [Parameter(Mandatory = $true)][ValidateSet('backend', 'frontend')][string]$Role,
        [Parameter(Mandatory = $true)][string]$ExpectedWorkingDirectory,
        [int]$ExpectedPort = 0,
        [switch]$RequireDbPath
    )

    if ($null -eq $Record) {
        return New-PqgProofResult -Status 'Incomplete' -Reason "$Role record is missing"
    }
    $required = @('pid', 'processStartTime', 'workingDirectory', 'command', 'identityMarker', 'executable', 'port')
    if ($RequireDbPath) { $required += 'dbPath' }
    foreach ($name in $required) {
        if (-not (Test-PqgHasProperty $Record $name)) {
            return New-PqgProofResult -Status 'Incomplete' -Reason "$Role record is missing $name"
        }
    }

    $pidValue = [int]$Record.pid
    $portValue = [int]$Record.port
    if ($pidValue -le 0 -or $portValue -le 0 -or $portValue -gt 65535) {
        return New-PqgProofResult -Status 'Incomplete' -Reason "$Role PID or port is invalid"
    }
    if ($ExpectedPort -gt 0 -and $portValue -ne $ExpectedPort) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role port does not match the expected port"
    }
    if (-not (Test-PqgPathEqual ([string]$Record.workingDirectory) $ExpectedWorkingDirectory)) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role workingDirectory does not match"
    }
    if ([string]::IsNullOrWhiteSpace([string]$Record.command) -or
        [string]::IsNullOrWhiteSpace([string]$Record.identityMarker) -or
        [string]::IsNullOrWhiteSpace([string]$Record.executable)) {
        return New-PqgProofResult -Status 'Incomplete' -Reason "$Role command identity is incomplete"
    }
    if ($RequireDbPath -and [string]::IsNullOrWhiteSpace([string]$Record.dbPath)) {
        return New-PqgProofResult -Status 'Incomplete' -Reason 'backend dbPath is missing'
    }

    $expectedStart = [DateTimeOffset]::MinValue
    if (-not [DateTimeOffset]::TryParse([string]$Record.processStartTime, [ref]$expectedStart)) {
        return New-PqgProofResult -Status 'Incomplete' -Reason "$Role processStartTime is invalid"
    }

    $snapshot = Get-PqgProcessSnapshot -Pid $pidValue
    if ($null -eq $snapshot) {
        return New-PqgProofResult -Status 'NotRunning' -Reason "$Role PID is not running"
    }
    $actualStart = [DateTimeOffset]::Parse([string]$snapshot.processStartTime)
    if ($expectedStart.UtcDateTime.Ticks -ne $actualStart.UtcDateTime.Ticks) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role PID start-time does not match dev-state" -Snapshot $snapshot
    }
    if ([string]::IsNullOrWhiteSpace([string]$snapshot.executable) -or
        -not (Test-PqgPathEqual ([string]$Record.executable) ([string]$snapshot.executable))) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role executable does not match dev-state" -Snapshot $snapshot
    }
    $commandLine = [string]$snapshot.commandLine
    if ([string]::IsNullOrWhiteSpace($commandLine)) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role command line is unavailable" -Snapshot $snapshot
    }
    if ($commandLine.IndexOf([string]$Record.command, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role command does not match dev-state" -Snapshot $snapshot
    }
    if ($commandLine.IndexOf([string]$Record.identityMarker, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role repository/source identity marker does not match" -Snapshot $snapshot
    }

    return New-PqgProofResult -Status 'Match' -Reason "$Role process identity matches dev-state" -Snapshot $snapshot
}

function New-PqgProcessRecord {
    param(
        [Parameter(Mandatory = $true)][int]$Pid,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$IdentityMarker,
        [Parameter(Mandatory = $true)][int]$Port,
        [string]$DbPath
    )

    $snapshot = $null
    for ($attempt = 0; $attempt -lt 20 -and $null -eq $snapshot; $attempt++) {
        $snapshot = Get-PqgProcessSnapshot -Pid $Pid
        if ($null -eq $snapshot) { Start-Sleep -Milliseconds 100 }
    }
    if ($null -eq $snapshot -or [string]::IsNullOrWhiteSpace([string]$snapshot.executable)) {
        throw "Cannot capture process provenance for PID $Pid"
    }

    $record = [ordered]@{
        pid = $Pid
        processStartTime = [string]$snapshot.processStartTime
        workingDirectory = Get-PqgCanonicalPath $WorkingDirectory
        command = $Command
        identityMarker = $IdentityMarker
        executable = Get-PqgCanonicalPath ([string]$snapshot.executable)
        port = $Port
    }
    if (-not [string]::IsNullOrWhiteSpace($DbPath)) {
        $record.dbPath = Get-PqgCanonicalPath $DbPath
    }
    return [pscustomobject]$record
}

function ConvertTo-PqgSingleQuotedLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return ($Value -replace "'", "''")
}

function Test-PqgPortListener {
    param([Parameter(Mandatory = $true)][int]$Port)
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Get-PqgLikelyBackendListeners {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$PythonExecutable
    )

    $expectedPython = Get-PqgCanonicalPath $PythonExecutable
    $results = @()
    $connections = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue)
    foreach ($connection in $connections) {
        $ownerPid = [int]$connection.OwningProcess
        if ($ownerPid -le 0) { continue }
        $snapshot = Get-PqgProcessSnapshot -Pid $ownerPid
        if ($null -eq $snapshot -or [string]::IsNullOrWhiteSpace([string]$snapshot.executable)) { continue }
        if (-not (Test-PqgPathEqual ([string]$snapshot.executable) $expectedPython)) { continue }
        if ([string]$snapshot.commandLine -notmatch '(?i)uvicorn\s+app\.main:app') { continue }
        $results += [pscustomobject]@{
            pid = $ownerPid
            port = [int]$connection.LocalPort
            commandLine = [string]$snapshot.commandLine
        }
    }
    return $results
}

function Test-PqgProcessDescendant {
    param(
        [Parameter(Mandatory = $true)][int]$ChildPid,
        [Parameter(Mandatory = $true)][int]$AncestorPid
    )

    $current = $ChildPid
    for ($depth = 0; $depth -lt 16 -and $current -gt 0; $depth++) {
        if ($current -eq $AncestorPid) { return $true }
        $snapshot = Get-PqgProcessSnapshot -Pid $current
        if ($null -eq $snapshot) { return $false }
        $current = [int]$snapshot.parentPid
    }
    return $false
}

function Test-PqgExclusiveFileAccess {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = $null
    try {
        $stream = [System.IO.File]::Open(
            (Get-PqgCanonicalPath $Path),
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
        return $true
    } catch {
        return $false
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
    }
}
