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

function Get-PqgIdentityMarker {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('backend', 'frontend')][string]$Role,
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$SourceSha
    )

    $root = (Get-PqgCanonicalPath $RepositoryRoot).ToLowerInvariant()
    $material = "$Role`n$($SourceSha.ToLowerInvariant())`n$root"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($material)
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = $hasher.ComputeHash($bytes)
    } finally {
        $hasher.Dispose()
    }
    $hex = -join ($digest | ForEach-Object { $_.ToString('x2') })
    return "PQGDEV-$Role-$($SourceSha.ToLowerInvariant())-$($hex.Substring(0, 16))"
}

function Get-PqgPowerShellExecutable {
    $command = Get-Command powershell -ErrorAction Stop
    return Get-PqgCanonicalPath $command.Source
}

function Get-PqgConfiguredDbPath {
    param(
        [Parameter(Mandatory = $true)][string]$BackendDirectory,
        [Parameter(Mandatory = $true)][string]$PythonExecutable
    )

    if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
        throw 'Backend Python environment is required to resolve DB provenance.'
    }

    Push-Location $BackendDirectory
    try {
        $output = @(& $PythonExecutable -c "from app.settings import Settings; print(Settings().db_path_resolved)" 2>$null)
        if ($LASTEXITCODE -ne 0 -or $output.Count -eq 0) {
            throw 'Unable to resolve configured backend DB path.'
        }
        $candidate = ([string]$output[-1]).Trim()
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            throw 'Configured backend DB path is empty.'
        }
        return Get-PqgCanonicalPath $candidate
    } finally {
        Pop-Location
    }
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
    try {
        if ([int]$State.schemaVersion -ne 2) {
            return New-PqgProofResult -Status 'Incomplete' -Reason 'dev-state schemaVersion must be 2'
        }
    } catch {
        return New-PqgProofResult -Status 'Incomplete' -Reason 'dev-state schemaVersion is invalid'
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
    return New-PqgProofResult -Status 'Match' -Reason 'repository/source provenance matches'
}

function Get-PqgProcessSnapshot {
    param([Parameter(Mandatory = $true)][int]$ProcessId)

    if ($ProcessId -le 0) {
        return $null
    }
    $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if ($null -eq $cim) {
        return $null
    }
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return $null
    }

    $executable = [string]$cim.ExecutablePath
    if ([string]::IsNullOrWhiteSpace($executable)) {
        try { $executable = [string]$process.Path } catch { $executable = '' }
    }

    return [pscustomobject]@{
        pid = $ProcessId
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
        [Parameter(Mandatory = $true)][string]$ExpectedCommand,
        [Parameter(Mandatory = $true)][string]$ExpectedIdentityMarker,
        [Parameter(Mandatory = $true)][string]$ExpectedExecutable,
        [int]$ExpectedPort = 0,
        [string]$ExpectedDbPath,
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

    try {
        $processIdValue = [int]$Record.pid
        $portValue = [int]$Record.port
    } catch {
        return New-PqgProofResult -Status 'Incomplete' -Reason "$Role PID or port is invalid"
    }
    if ($processIdValue -le 0 -or $portValue -le 0 -or $portValue -gt 65535) {
        return New-PqgProofResult -Status 'Incomplete' -Reason "$Role PID or port is invalid"
    }
    if ($ExpectedPort -gt 0 -and $portValue -ne $ExpectedPort) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role port does not match the expected port"
    }
    if (-not (Test-PqgPathEqual ([string]$Record.workingDirectory) $ExpectedWorkingDirectory)) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role workingDirectory does not match"
    }
    if (-not [string]::Equals([string]$Record.command, $ExpectedCommand, [System.StringComparison]::Ordinal)) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role command identity does not match"
    }
    if (-not [string]::Equals([string]$Record.identityMarker, $ExpectedIdentityMarker, [System.StringComparison]::Ordinal)) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role repository/source identity marker does not match"
    }
    if (-not (Test-PqgPathEqual ([string]$Record.executable) $ExpectedExecutable)) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role executable identity does not match"
    }
    if ($RequireDbPath) {
        if ([string]::IsNullOrWhiteSpace([string]$Record.dbPath)) {
            return New-PqgProofResult -Status 'Incomplete' -Reason 'backend dbPath is missing'
        }
        if (-not [string]::IsNullOrWhiteSpace($ExpectedDbPath) -and
            -not (Test-PqgPathEqual ([string]$Record.dbPath) $ExpectedDbPath)) {
            return New-PqgProofResult -Status 'Mismatch' -Reason 'backend dbPath does not match the configured DB'
        }
    }

    $expectedStart = [DateTimeOffset]::MinValue
    if (-not [DateTimeOffset]::TryParse([string]$Record.processStartTime, [ref]$expectedStart)) {
        return New-PqgProofResult -Status 'Incomplete' -Reason "$Role processStartTime is invalid"
    }

    $snapshot = Get-PqgProcessSnapshot -ProcessId $processIdValue
    if ($null -eq $snapshot) {
        return New-PqgProofResult -Status 'NotRunning' -Reason "$Role PID is not running"
    }
    $actualStart = [DateTimeOffset]::Parse([string]$snapshot.processStartTime)
    if ($expectedStart.UtcDateTime.Ticks -ne $actualStart.UtcDateTime.Ticks) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role PID start-time does not match dev-state" -Snapshot $snapshot
    }
    if ([string]::IsNullOrWhiteSpace([string]$snapshot.executable) -or
        -not (Test-PqgPathEqual ([string]$snapshot.executable) $ExpectedExecutable)) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role live executable does not match" -Snapshot $snapshot
    }
    $commandLine = [string]$snapshot.commandLine
    if ([string]::IsNullOrWhiteSpace($commandLine)) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role command line is unavailable" -Snapshot $snapshot
    }
    if ($commandLine.IndexOf($ExpectedCommand, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role live command does not match" -Snapshot $snapshot
    }
    if ($commandLine.IndexOf($ExpectedIdentityMarker, [System.StringComparison]::Ordinal) -lt 0) {
        return New-PqgProofResult -Status 'Mismatch' -Reason "$Role live repository/source marker does not match" -Snapshot $snapshot
    }

    return New-PqgProofResult -Status 'Match' -Reason "$Role process identity matches dev-state" -Snapshot $snapshot
}

function New-PqgProcessRecord {
    param(
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$IdentityMarker,
        [Parameter(Mandatory = $true)][int]$Port,
        [string]$DbPath
    )

    $snapshot = $null
    for ($attempt = 0; $attempt -lt 20 -and $null -eq $snapshot; $attempt++) {
        $snapshot = Get-PqgProcessSnapshot -ProcessId $ProcessId
        if ($null -eq $snapshot) { Start-Sleep -Milliseconds 100 }
    }
    if ($null -eq $snapshot -or [string]::IsNullOrWhiteSpace([string]$snapshot.executable)) {
        throw "Cannot capture process provenance for PID $ProcessId"
    }

    $record = [ordered]@{
        pid = $ProcessId
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

function Test-PqgProcessDescendant {
    param(
        [Parameter(Mandatory = $true)][int]$ChildProcessId,
        [Parameter(Mandatory = $true)][int]$AncestorProcessId
    )

    $current = $ChildProcessId
    for ($depth = 0; $depth -lt 16 -and $current -gt 0; $depth++) {
        if ($current -eq $AncestorProcessId) { return $true }
        $snapshot = Get-PqgProcessSnapshot -ProcessId $current
        if ($null -eq $snapshot) { return $false }
        $current = [int]$snapshot.parentPid
    }
    return $false
}

function Test-PqgPortOwnedByProcessTree {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][int]$RootProcessId
    )

    $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) {
        return $false
    }
    foreach ($listener in $listeners) {
        $ownerProcessId = [int]$listener.OwningProcess
        if ($ownerProcessId -le 0 -or
            -not (Test-PqgProcessDescendant -ChildProcessId $ownerProcessId -AncestorProcessId $RootProcessId)) {
            return $false
        }
    }
    return $true
}

function Get-PqgLikelyBackendListeners {
    param([Parameter(Mandatory = $true)][string]$PythonExecutable)

    $expectedPython = Get-PqgCanonicalPath $PythonExecutable
    $results = @()
    $connections = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue)
    foreach ($connection in $connections) {
        $ownerProcessId = [int]$connection.OwningProcess
        if ($ownerProcessId -le 0) { continue }
        $snapshot = Get-PqgProcessSnapshot -ProcessId $ownerProcessId
        if ($null -eq $snapshot -or [string]::IsNullOrWhiteSpace([string]$snapshot.executable)) { continue }
        if (-not (Test-PqgPathEqual ([string]$snapshot.executable) $expectedPython)) { continue }
        if ([string]$snapshot.commandLine -notmatch '(?i)uvicorn\s+app\.main:app') { continue }
        $results += [pscustomobject]@{
            pid = $ownerProcessId
            port = [int]$connection.LocalPort
            commandLine = [string]$snapshot.commandLine
        }
    }
    return $results
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
