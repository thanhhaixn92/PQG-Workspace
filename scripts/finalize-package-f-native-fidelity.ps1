[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$EvidenceRoot
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$evidenceBase = [IO.Path]::GetFullPath((Join-Path $repo 'output\playwright'))
$EvidenceRoot = [IO.Path]::GetFullPath($EvidenceRoot)
$evidencePrefix = $evidenceBase.TrimEnd('\') + '\'
if (-not $EvidenceRoot.StartsWith($evidencePrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'EvidenceRoot must be beneath output/playwright.'
}

$metadataPath = Join-Path $EvidenceRoot 'run-metadata.json'
$manifestPath = Join-Path $EvidenceRoot 'native-fidelity-manifest.json'
$artifactManifestPath = Join-Path $EvidenceRoot 'native-artifact-manifest.jsonl'
$receiptPath = Join-Path $EvidenceRoot 'native-assertion-receipts.jsonl'
$exitCode = 1
$metadata = $null
$failures = [Collections.Generic.List[string]]::new()

$expected = [ordered]@{
    F01 = @{ screenshot='f01-tablet-dark.jpg'; width=1024; height=600; theme='dark'; state='baseline'; reduced_motion=$false; focus_visible=$false; drawer_opened=$false; escape_restored=$false; overflow=$false }
    F02 = @{ screenshot='f02-tablet-light.jpg'; width=1024; height=600; theme='light'; state='baseline'; reduced_motion=$false; focus_visible=$false; drawer_opened=$false; escape_restored=$false; overflow=$false }
    F03 = @{ screenshot='f03-mobile-light.jpg'; width=390; height=667; theme='light'; state='baseline'; reduced_motion=$false; focus_visible=$false; drawer_opened=$false; escape_restored=$false; overflow=$false }
    F04 = @{ screenshot='f04-desktop-light.jpg'; width=1440; height=900; theme='light'; state='baseline'; reduced_motion=$false; focus_visible=$false; drawer_opened=$false; escape_restored=$false; overflow=$false }
    F05 = @{ screenshot='f05-mobile-reduced-focus.jpg'; width=390; height=667; theme='dark'; state='reduced-motion-focus'; reduced_motion=$true; focus_visible=$true; drawer_opened=$false; escape_restored=$false; overflow=$false }
    F06 = @{ screenshot='f06-keyboard-drawer.jpg'; width=390; height=667; theme='dark'; state='keyboard-drawer'; reduced_motion=$false; focus_visible=$true; drawer_opened=$true; escape_restored=$true; overflow=$false }
    F07 = @{ screenshot='f07-reflow.jpg'; width=320; height=640; theme='dark'; state='reflow'; reduced_motion=$false; focus_visible=$false; drawer_opened=$false; escape_restored=$false; overflow=$false }
    F08 = @{ screenshot='f08-populated.jpg'; width=1440; height=900; theme='light'; state='populated'; reduced_motion=$false; focus_visible=$false; drawer_opened=$false; escape_restored=$false; overflow=$false }
    F09 = @{ screenshot='f09-running.jpg'; width=1440; height=900; theme='light'; state='running'; reduced_motion=$false; focus_visible=$false; drawer_opened=$false; escape_restored=$false; overflow=$false }
    F10 = @{ screenshot='f10-cancelled.jpg'; width=1440; height=900; theme='light'; state='cancelled'; reduced_motion=$false; focus_visible=$false; drawer_opened=$false; escape_restored=$false; overflow=$false }
    F11 = @{ screenshot='f11-409.jpg'; width=1440; height=900; theme='light'; state='scope-409'; reduced_motion=$false; focus_visible=$false; drawer_opened=$false; escape_restored=$false; overflow=$false }
    F12 = @{ screenshot='f12-offline.jpg'; width=1440; height=900; theme='light'; state='offline-retry'; reduced_motion=$false; focus_visible=$false; drawer_opened=$false; escape_restored=$false; overflow=$false }
    F13 = @{ screenshot='f13-pending-approval.jpg'; width=1440; height=900; theme='light'; state='pending-action-package-visual-only'; reduced_motion=$false; focus_visible=$false; drawer_opened=$false; escape_restored=$false; overflow=$false }
    F14 = @{ screenshot='f14-native-zoom.jpg'; width=1440; height=900; theme='native'; state='native-zoom'; reduced_motion=$false; focus_visible=$false; drawer_opened=$false; escape_restored=$false; overflow=$false }
}

$baseArtifacts = @(
    ($expected.GetEnumerator() | Where-Object Key -ne 'F14' | ForEach-Object { $_.Value.screenshot })
    'browser-console-redacted.json'
    'browser-network-redacted.json'
    'source-manifest.json'
    'native-fidelity-manifest.json'
    'generated-package-f-native-harness.py'
)
$zoomArtifacts = @('f14-native-zoom.jpg', 'browser-native-zoom-redacted.json')
$expectedSourcePaths = @(
    'scripts\start-package-f-native-fidelity.ps1'
    'scripts\finalize-package-f-native-fidelity.ps1'
    'scripts\stop-package-f-native-fidelity.ps1'
    'backend\app\db\migrations.py'
    'backend\app\main.py'
    'backend\app\api\assistant.py'
    'backend\app\api\action_packages.py'
    'backend\app\api\approvals.py'
    'backend\app\api\works.py'
    'frontend\src\App.tsx'
    'frontend\src\store\store.ts'
    'frontend\src\components\AssistantChatSidebar.tsx'
    'frontend\src\components\WorkHub.tsx'
    'frontend\src\components\ApprovalModal.tsx'
    'frontend\src\components\ActionPackagesPanel.tsx'
    'frontend\src\components\ReviewInboxPanel.tsx'
    'frontend\src\components\assistant\TurnPartRenderer.tsx'
    'frontend\src\assistant\threadStreamRegistry.ts'
    'frontend\src\api\assistant.ts'
    'frontend\src\api\actionPackages.ts'
    'frontend\src\api\approvals.ts'
    'frontend\src\index.css'
)

function Add-Failure([string]$Message) { $failures.Add($Message) }

function Read-JsonLines([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return @() }
    return @(Get-Content -Encoding utf8 -LiteralPath $Path |
        Where-Object { $_.Trim() } |
        ForEach-Object { $_ | ConvertFrom-Json -ErrorAction Stop })
}

function Get-JpegInfo([string]$Path) {
    $bytes = [IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 16 -or $bytes[0] -ne 0xff -or $bytes[1] -ne 0xd8 -or
        $bytes[$bytes.Length - 2] -ne 0xff -or $bytes[$bytes.Length - 1] -ne 0xd9) { return $null }
    try {
        Add-Type -AssemblyName System.Drawing
        $stream = [IO.MemoryStream]::new($bytes)
        try {
            $image = [Drawing.Image]::FromStream($stream, $true, $true)
            try { return @{ width=$image.Width; height=$image.Height } }
            finally { $image.Dispose() }
        } finally { $stream.Dispose() }
    } catch { return $null }
}

function Test-EqualBoolean($Actual, [bool]$ExpectedValue) { return [bool]$Actual -eq $ExpectedValue }
function Save-Metadata { $metadata | ConvertTo-Json -Depth 20 | Set-Content -Encoding utf8 -LiteralPath $metadataPath }
function Set-ObjectProperty($Object, [string]$Name, $Value) {
    $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
}

try {
    $metadata = Get-Content -Raw -Encoding utf8 -LiteralPath $metadataPath | ConvertFrom-Json
    $manifest = Get-Content -Raw -Encoding utf8 -LiteralPath $manifestPath | ConvertFrom-Json
    if ($metadata.package -ne 'F' -or $metadata.support_route -ne 'native-browser-computer-use' -or
        $metadata.status -ne 'AWAITING_NATIVE_BROWSER_FIDELITY' -or $manifest.run_id -ne $metadata.run_id) {
        throw 'Package F run identity or lifecycle state is invalid.'
    }

    $receipts = @(Read-JsonLines $receiptPath)
    $records = @(Read-JsonLines $artifactManifestPath)
    $expectedIds = @($expected.Keys)
    if (@($receipts | Where-Object { $_.assertion_id -notin $expectedIds }).Count) { Add-Failure 'Unknown receipt ID exists.' }
    $f14Receipts = @($receipts | Where-Object assertion_id -eq 'F14')
    $f14Pass = $f14Receipts.Count -eq 1 -and $f14Receipts[0].status -eq 'PASS'
    $requiredArtifacts = @($baseArtifacts)
    if ($f14Pass) { $requiredArtifacts += $zoomArtifacts }
    $allowedArtifacts = @($baseArtifacts + $zoomArtifacts)

    foreach ($group in @($records | Group-Object filename)) {
        if ($group.Count -ne 1) { Add-Failure "Artifact manifest contains duplicate filename: $($group.Name)" }
    }
    foreach ($name in $requiredArtifacts) {
        if (@($records | Where-Object { $_.filename -eq $name -and $_.run_id -eq $metadata.run_id }).Count -ne 1) {
            Add-Failure "Required artifact is missing or duplicated: $name"
        }
    }

    $jpegInfo = @{}
    foreach ($record in $records) {
        $name = [string]$record.filename
        $path = Join-Path $EvidenceRoot $name
        if ($record.run_id -ne $metadata.run_id -or $name -notin $allowedArtifacts -or
            [IO.Path]::GetFileName($name) -ne $name -or $record.sha256 -notmatch '^[0-9a-f]{64}$' -or
            -not (Test-Path -LiteralPath $path) -or
            (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant() -ne $record.sha256) {
            Add-Failure "Invalid or unknown artifact: $name"
            continue
        }
        if ($name.EndsWith('.jpg')) {
            $info = Get-JpegInfo $path
            if (-not $info) { Add-Failure "JPEG cannot be decoded: $name" }
            else { $jpegInfo[$name] = $info }
        }
    }

    $consolePath = Join-Path $EvidenceRoot 'browser-console-redacted.json'
    if (Test-Path -LiteralPath $consolePath) {
        try {
            $console = Get-Content -Raw -Encoding utf8 -LiteralPath $consolePath | ConvertFrom-Json
            if ($null -eq $console.entries) { Add-Failure 'Console artifact lacks entries array.' }
            if (@($console.entries | Where-Object { ([string]$_.level).ToLowerInvariant() -in @('error','fatal') }).Count) {
                Add-Failure 'Browser console contains error or fatal entries.'
            }
        } catch { Add-Failure "Console JSON is invalid: $($_.Exception.Message)" }
    }

    $networkPath = Join-Path $EvidenceRoot 'browser-network-redacted.json'
    if (Test-Path -LiteralPath $networkPath) {
        try {
            $network = Get-Content -Raw -Encoding utf8 -LiteralPath $networkPath | ConvertFrom-Json
            if ($null -eq $network.requests) { Add-Failure 'Network artifact lacks requests array.' }
            if (@($network.requests | Where-Object {
                -not ([string]$_.url).StartsWith('http://127.0.0.1:') -and
                -not ([string]$_.url).StartsWith('http://localhost:')
            }).Count) { Add-Failure 'Browser network contains a non-loopback request.' }
        } catch { Add-Failure "Network JSON is invalid: $($_.Exception.Message)" }
    }

    $manifestAssertions = @($manifest.assertions)
    if ($manifest.schema_version -ne 3 -or $manifestAssertions.Count -ne 14) { Add-Failure 'Native fidelity manifest schema/count is invalid.' }
    foreach ($id in $expectedIds) {
        $cell = $expected[$id]
        $manifestHit = @($manifestAssertions | Where-Object id -eq $id)
        if ($manifestHit.Count -ne 1) { Add-Failure "$id requires exactly one canonical manifest cell."; continue }
        $manifestCell = $manifestHit[0]
        if ($manifestCell.screenshot -ne $cell.screenshot -or [int]$manifestCell.width -ne $cell.width -or
            [int]$manifestCell.height -ne $cell.height -or $manifestCell.theme -ne $cell.theme -or
            $manifestCell.state -ne $cell.state -or
            -not (Test-EqualBoolean $manifestCell.reduced_motion $cell.reduced_motion) -or
            -not (Test-EqualBoolean $manifestCell.focus_visible $cell.focus_visible) -or
            -not (Test-EqualBoolean $manifestCell.drawer_opened $cell.drawer_opened) -or
            -not (Test-EqualBoolean $manifestCell.escape_restored $cell.escape_restored) -or
            -not (Test-EqualBoolean $manifestCell.overflow $cell.overflow)) {
            Add-Failure "$id native manifest cell differs from the finalizer contract."
        }
    }

    $sourcePath = Join-Path $EvidenceRoot 'source-manifest.json'
    $source = Get-Content -Raw -Encoding utf8 -LiteralPath $sourcePath | ConvertFrom-Json
    $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourcePath).Hash.ToLowerInvariant()
    $sourceEntries = @($source.files)
    $actualSourcePaths = @($sourceEntries | ForEach-Object { [string]$_.path } | Sort-Object)
    $canonicalSourcePaths = @($expectedSourcePaths | Sort-Object)
    if ($source.run_id -ne $metadata.run_id -or
        @($sourceEntries | Group-Object path | Where-Object Count -ne 1).Count -or
        @(Compare-Object $canonicalSourcePaths $actualSourcePaths).Count) {
        Add-Failure 'Source manifest identity, coverage, or uniqueness is invalid.'
    }
    foreach ($entry in $sourceEntries) {
        $sourceFile = Join-Path $repo $entry.path
        if (-not (Test-Path -LiteralPath $sourceFile) -or
            (Get-FileHash -Algorithm SHA256 -LiteralPath $sourceFile).Hash.ToLowerInvariant() -ne $entry.sha256) {
            Add-Failure "Source changed after start: $($entry.path)"
        }
    }

    foreach ($id in $expectedIds) {
        $cell = $expected[$id]
        $hits = @($receipts | Where-Object assertion_id -eq $id)
        if ($hits.Count -ne 1) { Add-Failure "$id requires exactly one receipt."; continue }
        $receipt = $hits[0]
        if ($receipt.run_id -ne $metadata.run_id -or $receipt.cell_id -ne $id -or
            $receipt.source_manifest_sha -ne $sourceHash) {
            Add-Failure "$id receipt identity/source binding is invalid."
            continue
        }
        if ($id -eq 'F14' -and $receipt.status -eq 'NOT_RUN') { continue }
        if ($receipt.status -ne 'PASS') { Add-Failure "$id is not PASS."; continue }
        if ([int]$receipt.viewport.width -ne $cell.width -or [int]$receipt.viewport.height -ne $cell.height -or
            $receipt.theme -ne $cell.theme -or $receipt.state -ne $cell.state -or
            -not (Test-EqualBoolean $receipt.reduced_motion $cell.reduced_motion) -or
            -not (Test-EqualBoolean $receipt.focus_visible $cell.focus_visible) -or
            -not (Test-EqualBoolean $receipt.drawer_opened $cell.drawer_opened) -or
            -not (Test-EqualBoolean $receipt.escape_restored $cell.escape_restored) -or
            -not (Test-EqualBoolean $receipt.overflow $cell.overflow)) {
            Add-Failure "$id receipt differs from the canonical matrix."
        }
        if ($id -eq 'F14') {
            if ([int]$receipt.client_width -lt 1 -or [int]$receipt.client_width -gt $cell.width -or
                [int]$receipt.scroll_width -ne [int]$receipt.client_width) {
                Add-Failure 'F14 native zoom reports invalid CSS viewport/reflow geometry.'
            }
            $expectedCaptureWidth = $cell.width
            $expectedCaptureHeight = $cell.height
        } else {
            if ([int]$receipt.client_width -ne $cell.width -or [int]$receipt.scroll_width -ne $cell.width) {
                Add-Failure "$id reports horizontal overflow or an incorrect client width."
            }
            $expectedCaptureWidth = [int][math]::Round($cell.width * [double]$receipt.device_pixel_ratio)
            $expectedCaptureHeight = [int][math]::Round($cell.height * [double]$receipt.device_pixel_ratio)
        }
        $image = $jpegInfo[$cell.screenshot]
        if (-not $image -or [int]$receipt.capture_width -ne $expectedCaptureWidth -or
            [int]$receipt.capture_height -ne $expectedCaptureHeight -or
            $image.width -ne $expectedCaptureWidth -or $image.height -ne $expectedCaptureHeight) {
            Add-Failure "$id screenshot dimensions do not match viewport and devicePixelRatio."
        }

        $evidenceNames = @($receipt.evidence | Sort-Object -Unique)
        $hashNames = @($receipt.artifact_hashes.PSObject.Properties.Name | Sort-Object -Unique)
        if (@($receipt.evidence).Count -ne $evidenceNames.Count -or
            @(Compare-Object $evidenceNames $hashNames).Count -or $cell.screenshot -notin $evidenceNames) {
            Add-Failure "$id evidence and artifact_hashes keys do not match exactly."
        }
        foreach ($name in $evidenceNames) {
            $hash = [string]$receipt.artifact_hashes.PSObject.Properties[$name].Value
            if (@($records | Where-Object { $_.filename -eq $name -and $_.sha256 -eq $hash -and $_.run_id -eq $metadata.run_id }).Count -ne 1) {
                Add-Failure "$id evidence hash is not bound to exactly one artifact: $name"
            }
        }
        if ($id -in @('F05','F06') -and -not ([string]$receipt.focus_target).Trim()) {
            Add-Failure "$id requires a named visible/restored focus target."
        }
        if ($id -eq 'F11') {
            $screenshotRecord = @($records | Where-Object filename -eq $cell.screenshot)[0]
            if (-not $receipt.prompt_preserved -or [int]$receipt.controlled_409_count -lt 1 -or
                [int]$receipt.server_observation.controlled_409 -lt 1 -or [int]$screenshotRecord.controlled_409 -lt 1) {
                Add-Failure 'F11 is not bound to the controlled 409 and preserved prompt.'
            }
        }
        if ($id -eq 'F12') {
            $screenshotRecord = @($records | Where-Object filename -eq $cell.screenshot)[0]
            $history = @($receipt.server_observation.offline_history)
            if (-not $receipt.offline_enabled_observed -or -not $receipt.retry_recovered -or
                -not [bool]$screenshotRecord.offline -or [bool]$receipt.server_observation.offline -or
                $history.Count -lt 2 -or -not [bool]$history[-2].enabled -or [bool]$history[-1].enabled) {
                Add-Failure 'F12 is not bound to an offline capture followed by controlled recovery.'
            }
        }
        if ($id -eq 'F13') {
            if ($receipt.server_observation.fixture.package_id -notlike 'package-f-action-*' -or
                $receipt.server_observation.fixture.approval_id -notlike 'package-f-approval-*') {
                Add-Failure 'F13 receipt was recorded before the staged pending fixture existed.'
            }
        }
        if ($id -eq 'F14' -and ([int]$receipt.native_zoom_percent -ne 200 -or -not $receipt.browser_version -or
            -not $receipt.browser_profile -or 'browser-native-zoom-redacted.json' -notin $evidenceNames)) {
            Add-Failure 'F14 native 200 percent zoom evidence is incomplete.'
        }
    }

    $f12Receipt = @($receipts | Where-Object assertion_id -eq 'F12')
    $f13Receipt = @($receipts | Where-Object assertion_id -eq 'F13')
    if ($f12Receipt.Count -eq 1 -and $f13Receipt.Count -eq 1) {
        if ([int64]$f13Receipt[0].recorded_at -lt [int64]$f12Receipt[0].recorded_at -or
            [int64]$f13Receipt[0].server_observation.fixture.seeded_at -lt [int64]$f12Receipt[0].recorded_at -or
            [int64]$f13Receipt[0].server_observation.fixture.after_f12_recorded_at -ne [int64]$f12Receipt[0].recorded_at) {
            Add-Failure 'F13 staging order must be validated F12 receipt, fixture seed, then F13 receipt.'
        }
    }

    if ($f14Pass) {
        try {
            $zoom = Get-Content -Raw -Encoding utf8 -LiteralPath (Join-Path $EvidenceRoot 'browser-native-zoom-redacted.json') | ConvertFrom-Json
            if ([int]$zoom.zoom_percent -ne 200 -or -not $zoom.browser_version -or -not $zoom.browser_profile -or
                $zoom.run_id -ne $metadata.run_id) { Add-Failure 'Native zoom JSON schema/binding is invalid.' }
        } catch { Add-Failure "Native zoom JSON is invalid: $($_.Exception.Message)" }
    }

    $observation = Invoke-RestMethod -Uri "$($metadata.urls.backend)/_package_f/observe" -TimeoutSec 10
    $observationPath = Join-Path $EvidenceRoot 'final-observation-redacted.json'
    $observation | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 -LiteralPath $observationPath
    Set-ObjectProperty $metadata.browser_uat 'final_observation' @{
        path = $observationPath
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $observationPath).Hash.ToLowerInvariant()
    }
    if ([int]$observation.provider_bound_run_attempts -ne 0 -or
        [int]$observation.browser_action_mutations -ne 0 -or
        [int]$observation.browser_approval_decisions -ne 0 -or [int]$observation.executor_runs -ne 0) {
        Add-Failure 'Observer reports a forbidden provider-bound or governed mutation attempt.'
    }
    $fixture = $observation.fixture
    if ($fixture.package_id -notlike 'package-f-action-*' -or
        $fixture.approval_id -notlike 'package-f-approval-*' -or
        $fixture.package_status -ne 'awaiting_approval' -or
        $fixture.package_title -ne 'PACKAGE-F-PENDING-APPROVAL' -or
        [int]$fixture.pending_step_count -ne 1 -or $fixture.approval_status -ne 'pending' -or
        $fixture.approval_target -ne $fixture.package_id) {
        Add-Failure 'Synthetic pending Action Package fixture changed or is invalid.'
    }
    if ([int]$observation.synthetic_turns -ne 2 -or [int]$observation.fixture_seeded_action_packages -ne 1 -or
        [int]$observation.fixture_seeded_approvals -ne 1) {
        Add-Failure 'Synthetic fixture counts differ from the isolated baseline.'
    }
    $offlineHistory = @($observation.offline_history)
    if ($offlineHistory.Count -lt 2 -or -not [bool]$offlineHistory[-2].enabled -or [bool]$offlineHistory[-1].enabled) {
        Add-Failure 'Final offline history does not end with enable then successful recovery.'
    }

    $metadata.passed_assertion_count = @($receipts | Where-Object { $_.assertion_id -in $expectedIds -and $_.status -eq 'PASS' }).Count
    if ($failures.Count) {
        $metadata.status = 'FAIL'; $metadata.browser_uat.status = 'FAIL'
        Set-ObjectProperty $metadata 'failure' @{ stage='finalizer'; messages=@($failures) }
        $exitCode = 1
    } elseif ($metadata.passed_assertion_count -eq 14) {
        $metadata.status = 'PASS'; $metadata.browser_uat.status = 'PASS'; $exitCode = 0
    } else {
        $metadata.status = 'PARTIAL'; $metadata.browser_uat.status = 'PARTIAL'
        Set-ObjectProperty $metadata.browser_uat 'reason' 'F14 native zoom is NOT_RUN; incomplete non-green.'
        $exitCode = 2
    }
    Set-ObjectProperty $metadata.browser_uat 'finalized_at' (Get-Date).ToString('o')
    $metadata.completed_at = (Get-Date).ToString('o')
    Save-Metadata
} catch {
    if ($metadata) {
        $metadata.status = 'FAIL'; $metadata.completed_at = (Get-Date).ToString('o')
        Set-ObjectProperty $metadata 'failure' @{ stage='finalizer-unhandled'; messages=@($_.Exception.Message); stack=$_.ScriptStackTrace }
        Save-Metadata
    }
    $exitCode = 1
} finally {
    try {
        & (Join-Path $PSScriptRoot 'stop-package-f-native-fidelity.ps1') -EvidenceRoot $EvidenceRoot -PreserveTerminalStatus
        if ($LASTEXITCODE -ne 0) { $exitCode = 1 }
    } catch { $exitCode = 1 }
}

exit $exitCode
