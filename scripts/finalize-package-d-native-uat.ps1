[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$EvidenceRoot
)

# Finalizes only the matching native Package D fixture. A PASS requires every
# manifest assertion receipt and a final observation proving no product mutation.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$evidenceBase = [System.IO.Path]::GetFullPath((Join-Path $repo 'output\playwright'))
$EvidenceRoot = [System.IO.Path]::GetFullPath($EvidenceRoot)
$evidencePrefix = $evidenceBase.TrimEnd('\') + '\'
if (-not $EvidenceRoot.StartsWith($evidencePrefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'EvidenceRoot must be beneath output/playwright.' }
if (-not (Split-Path -Leaf $EvidenceRoot).StartsWith('package-d-native-', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'EvidenceRoot leaf must start with package-d-native-.' }

$metadataPath = Join-Path $EvidenceRoot 'run-metadata.json'
$manifestPath = Join-Path $EvidenceRoot 'native-uat-manifest.json'
$metadata = $null
$terminalExit = 1
try {
if (-not (Test-Path -LiteralPath $metadataPath) -or -not (Test-Path -LiteralPath $manifestPath)) { throw 'Native Package D metadata or manifest is missing.' }
$metadata = Get-Content -Raw -Encoding utf8 -LiteralPath $metadataPath | ConvertFrom-Json
$manifest = Get-Content -Raw -Encoding utf8 -LiteralPath $manifestPath | ConvertFrom-Json
if ($metadata.package -ne 'D' -or $metadata.support_route -ne 'native-browser-computer-use') { throw 'Metadata is not from the Package D native support starter.' }
if ($metadata.status -ne 'AWAITING_BROWSER_UAT') { throw "Native Package D run is not awaiting browser UAT: $($metadata.status)" }
if (-not $metadata.run_id -or $manifest.run_id -ne $metadata.run_id) { throw 'Native Package D run identity does not match its manifest.' }
function Fail-FinalizerAndCleanup([string]$Message) {
    throw $Message
}

$failures = [System.Collections.Generic.List[string]]::new()
$allowedArtifactNames = @('desktop-sidebar-workhub-a1.jpg', 'desktop-sidebar-workhub-a2-late.jpg', 'desktop-sidebar-workhub-a2-error.jpg', 'desktop-sidebar-workhub-b1-active.jpg', 'desktop-sidebar-workhub-b1-done.jpg', 'mobile-sidebar-workhub-a1.jpg', 'mobile-sidebar-workhub-a2-late.jpg', 'mobile-sidebar-workhub-a2-error.jpg', 'mobile-sidebar-workhub-b1-active.jpg', 'mobile-sidebar-workhub-b1-done.jpg', 'browser-console-redacted.json', 'browser-network-redacted.json')
$artifactManifestPath = Join-Path $EvidenceRoot 'native-artifact-manifest.jsonl'
$artifactRecords = @()
if (Test-Path -LiteralPath $artifactManifestPath) {
    try { $artifactRecords = @(Get-Content -Encoding utf8 -LiteralPath $artifactManifestPath | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json }) }
    catch { $failures.Add("Artifact manifest is not valid JSONL: $($_.Exception.Message)") }
}
$canonicalEvidenceRoot = [System.IO.Path]::GetFullPath($EvidenceRoot).TrimEnd('\') + '\'
function Test-RecordedArtifact([string]$Name, [string]$ExpectedHash) {
    if ($Name -notin $allowedArtifactNames -or [System.IO.Path]::GetFileName($Name) -ne $Name) { return $false }
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $EvidenceRoot $Name))
    if (-not $candidate.StartsWith($canonicalEvidenceRoot, [System.StringComparison]::OrdinalIgnoreCase)) { return $false }
    if (-not $ExpectedHash -or $ExpectedHash -notmatch '^[0-9a-f]{64}$' -or -not (Test-Path -LiteralPath $candidate)) { return $false }
    $records = @($artifactRecords | Where-Object { $_.run_id -eq $metadata.run_id -and $_.filename -eq $Name -and $_.sha256 -eq $ExpectedHash })
    if ($records.Count -ne 1) { return $false }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $candidate).Hash.ToLowerInvariant() -ne $ExpectedHash) { return $false }
    $bytes = [System.IO.File]::ReadAllBytes($candidate)
    if ($Name.EndsWith('.jpg')) {
        try {
            Add-Type -AssemblyName System.Drawing
            $stream = [System.IO.MemoryStream]::new($bytes)
            try { $image = [System.Drawing.Image]::FromStream($stream, $true, $true); return $image.Width -gt 0 -and $image.Height -gt 0 }
            finally { if ($image) { $image.Dispose() }; $stream.Dispose() }
        } catch { return $false }
    }
    try { $document = [System.Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json } catch { return $false }
    if ($Name -eq 'browser-console-redacted.json') {
        if ($null -eq $document.entries -or $document.entries -isnot [System.Collections.IEnumerable]) { return $false }
        return @($document.entries | Where-Object { $_ -isnot [pscustomobject] -or ([string]$_.level).ToLowerInvariant() -in @('error', 'fatal') }).Count -eq 0
    }
    if ($Name -eq 'browser-network-redacted.json') {
        if ($null -eq $document.requests -or $document.requests -isnot [System.Collections.IEnumerable]) { return $false }
        return @($document.requests | Where-Object { $_ -isnot [pscustomobject] -or -not ([string]$_.url).StartsWith('http://127.0.0.1:') -and -not ([string]$_.url).StartsWith('http://localhost:') }).Count -eq 0
    }
    return $false
}
function Get-RequiredArtifacts([string]$AssertionId) {
    $parts = $AssertionId -split '-'
    if ($parts[1] -eq 'global') { return @('browser-network-redacted.json') }
    $sequence = [int]$parts[2]
    if ($sequence -le 6) { return @("$($parts[1])-sidebar-workhub-a1.jpg") }
    if ($sequence -le 9) { return @("$($parts[1])-sidebar-workhub-a2-late.jpg") }
    if ($sequence -eq 10) { return @("$($parts[1])-sidebar-workhub-a2-error.jpg") }
    if ($sequence -le 13) { return @("$($parts[1])-sidebar-workhub-b1-active.jpg") }
    if ($sequence -eq 14) { return @("$($parts[1])-sidebar-workhub-b1-done.jpg") }
    return @('browser-console-redacted.json', 'browser-network-redacted.json')
}
$expected = @($manifest.assertions | ForEach-Object { [string]$_.id })
if ($expected.Count -ne $metadata.planned_assertion_count) { $failures.Add('Manifest assertion count does not match planned_assertion_count.') }
$receiptPath = Join-Path $EvidenceRoot 'native-assertion-receipts.jsonl'
$receipts = @()
if (Test-Path -LiteralPath $receiptPath) {
    try { $receipts = @(Get-Content -Encoding utf8 -LiteralPath $receiptPath | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json -ErrorAction Stop }) }
    catch { Fail-FinalizerAndCleanup "Receipt JSONL is invalid: $($_.Exception.Message)" }
}
foreach ($id in $expected) {
    $receiptMatches = @($receipts | Where-Object { $_.assertion_id -eq $id })
    if ($receiptMatches.Count -ne 1) { $failures.Add("$id requires exactly one receipt; found $($receiptMatches.Count).") }
    elseif ($receiptMatches[0].status -ne 'PASS') { $failures.Add("$id receipt status is $($receiptMatches[0].status), not PASS.") }
    elseif ($receiptMatches[0].run_id -ne $metadata.run_id) { $failures.Add("$id receipt has a foreign run identity.") }
    elseif ($receiptMatches[0].viewport -ne ($id -split '-')[1]) { $failures.Add("$id receipt viewport does not match assertion id.") }
    elseif (-not @($receiptMatches[0].evidence).Count) { $failures.Add("$id receipt has no evidence reference.") }
    else {
        foreach ($requiredArtifact in @(Get-RequiredArtifacts $id)) {
            if ($requiredArtifact -notin @($receiptMatches[0].evidence)) { $failures.Add("$id receipt is missing its assertion-specific artifact: $requiredArtifact") }
        }
        if ($id -match '-(?:06|13)$') {
            $expectedThread = if ($id.EndsWith('-06')) { $metadata.fixture.threadA1.id } else { $metadata.fixture.threadB1.id }
            $streamSnapshot = $receiptMatches[0].observed_stream_subscriptions
            if ($null -eq $streamSnapshot -or @($streamSnapshot.PSObject.Properties).Count -ne 1 -or [int]$streamSnapshot.PSObject.Properties[$expectedThread].Value -ne 1) { $failures.Add("$id does not contain the server-recorded exactly-one SSE observation.") }
        }
        if ($id.EndsWith('-14') -and $receiptMatches[0].observed_turn_status -ne 'completed') { $failures.Add("$id does not contain the server-recorded completed turn status.") }
        foreach ($artifactName in @($receiptMatches[0].evidence)) {
            $hashProperty = @($receiptMatches[0].artifact_hashes.PSObject.Properties | Where-Object { $_.Name -eq $artifactName } | Select-Object -First 1)
            if ($hashProperty.Count -ne 1) { $failures.Add("$id receipt is missing its evidence hash: $artifactName") }
            elseif (-not (Test-RecordedArtifact $artifactName ([string]$hashProperty[0].Value))) { $failures.Add("$id receipt references an invalid, unrecorded, or mismatched artifact: $artifactName") }
        }
    }
}
if (@($receipts | Where-Object { $_.assertion_id -notin $expected }).Count) { $failures.Add('Receipt file contains an unknown assertion id.') }
foreach ($requiredArtifact in @($metadata.browser_uat.evidence_required)) {
    $records = @($artifactRecords | Where-Object { $_.run_id -eq $metadata.run_id -and $_.filename -eq $requiredArtifact })
    if ($records.Count -ne 1) { $failures.Add("Required native Browser artifact is missing, unrecorded, or invalid: $requiredArtifact") }
    elseif (-not (Test-RecordedArtifact $requiredArtifact ([string]$records[0].sha256))) { $failures.Add("Required native Browser artifact is missing, unrecorded, or invalid: $requiredArtifact") }
}

try {
    $observation = Invoke-RestMethod -Uri "$($metadata.urls.backend)/_package_d/observe" -TimeoutSec 10
    $observation | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 -LiteralPath (Join-Path $EvidenceRoot 'final-observation-redacted.json')
    if (@($observation.product_post_paths.PSObject.Properties).Count -ne 0) { $failures.Add('Observation reports product POST paths.') }
    if ($observation.action_packages -ne 0 -or $observation.approvals -ne 0) { $failures.Add('Observation reports an Action Package or approval.') }
    if ($observation.synthetic_turns -ne 4) { $failures.Add("Observation expected four synthetic turns; found $($observation.synthetic_turns).") }
} catch {
    $failures.Add("Final observation failed: $($_.Exception.Message)")
}

$passedAssertionCount = 0
foreach ($id in $expected) {
    if (@($receipts | Where-Object { $_.assertion_id -eq $id -and $_.status -eq 'PASS' }).Count -eq 1) { $passedAssertionCount++ }
}
$metadata.passed_assertion_count = $passedAssertionCount
$failureCount = $failures.Count
$metadata.browser_uat = @{ status = if ($failureCount) { 'FAIL' } else { 'PASS' }; finalized_at = (Get-Date).ToString('o'); failure_count = $failureCount }
$metadata.status = if ($failureCount) { 'FAIL' } else { 'PASS' }
$metadata.completed_at = (Get-Date).ToString('o')
if ($failureCount) { $metadata | Add-Member -NotePropertyName failure -NotePropertyValue @{ stage = 'finalizer'; messages = @($failures) } -Force }
$metadata | ConvertTo-Json -Depth 16 | Set-Content -Encoding utf8 -LiteralPath $metadataPath
$terminalExit = if ($failureCount -gt 0) { 1 } else { 0 }
} catch {
    if ($null -ne $metadata -and $metadata.package -eq 'D' -and $metadata.support_route -eq 'native-browser-computer-use') {
        $metadata.status = 'FAIL'
        $metadata.completed_at = (Get-Date).ToString('o')
        $metadata | Add-Member -NotePropertyName failure -NotePropertyValue @{ stage='finalizer-unhandled'; messages=@($_.Exception.Message, $_.ScriptStackTrace) } -Force
        try { $metadata | ConvertTo-Json -Depth 16 | Set-Content -Encoding utf8 -LiteralPath $metadataPath } catch { }
    }
    $terminalExit = 1
} finally {
    & (Join-Path $PSScriptRoot 'stop-package-d-native-uat.ps1') -EvidenceRoot $EvidenceRoot -PreserveTerminalStatus
    if (-not $?) { $terminalExit = 1 }
}
exit $terminalExit
