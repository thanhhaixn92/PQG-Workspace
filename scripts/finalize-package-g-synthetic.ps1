[CmdletBinding(DefaultParameterSetName='Evaluator')]
param(
    [Parameter(Mandatory, ParameterSetName='Evaluator')][string]$EvidenceRoot,
    [Parameter(Mandatory, ParameterSetName='Aggregate')][string[]]$ReceiptRoots,
    [Parameter(Mandatory, ParameterSetName='Aggregate')][string]$AggregateEvidenceRoot
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$base = [IO.Path]::GetFullPath((Join-Path $repo 'output\playwright'))

function Assert-UnderEvidenceBase([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($base.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Evidence path must be beneath output/playwright.' }
    return $full
}
function Save-Json($Value, [string]$Path) { $Value | ConvertTo-Json -Depth 20 | Set-Content -Encoding utf8 -LiteralPath $Path }
function Get-FileSha256([string]$Path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant() }
function Get-Task($Receipt, [int]$Number) {
    $property = $Receipt.tasks.PSObject.Properties["task_$Number"]
    if (-not $property) { throw "Receipt is missing task_$Number." }
    $task = $property.Value
    if ($task.status -notin @('PASS','FAIL','NOT_RUN') -or $null -eq $task.duration_seconds -or [int]$task.duration_seconds -lt 0 -or $null -eq $task.hint_count -or [int]$task.hint_count -lt 0 -or -not $task.evidence -or @($task.evidence).Count -eq 0) { throw "Receipt task_$Number is incomplete." }
    return $task
}
function Test-EvaluatorReceipt([string]$Root, [switch]$Finalize) {
    $root = Assert-UnderEvidenceBase $Root
    $metadataPath = Join-Path $root 'run-metadata.json'
    $receiptPath = Join-Path $root 'g-synthetic-receipt.json'
    if (-not (Test-Path -LiteralPath $metadataPath) -or -not (Test-Path -LiteralPath $receiptPath)) { throw 'Evaluator metadata or receipt is missing.' }
    $metadata = Get-Content -Raw -Encoding utf8 -LiteralPath $metadataPath | ConvertFrom-Json
    $receipt = Get-Content -Raw -Encoding utf8 -LiteralPath $receiptPath | ConvertFrom-Json
    $receiptFingerprint = if ($receipt.source_fingerprint_sha256) { $receipt.source_fingerprint_sha256 } else { $receipt.fingerprint }
    if ($metadata.package -ne 'F' -or -not $metadata.fixture.g_synthetic -or $metadata.run_id -ne $receipt.run_id -or $metadata.source_fingerprint_sha256 -ne $receiptFingerprint) { throw 'Receipt does not bind to a G-SYNTHETIC run and fingerprint.' }
    if ($receipt.evaluation_type -ne 'synthetic agent evaluation' -or $receipt.evaluator_id -notmatch '^A0[1-5]$' -or -not $receipt.browser_profile) { throw 'Receipt evaluation identity is invalid.' }
    $flags = if ($receipt.restricted_interaction_flags) { @{source_access=$receipt.restricted_interaction_flags.source_or_test_read;private_control_endpoint_access=$receipt.restricted_interaction_flags.private_endpoint_called;real_provider_access=$receipt.restricted_interaction_flags.provider_called;approval_interaction=$receipt.restricted_interaction_flags.approval_interacted;executor_interaction=$receipt.restricted_interaction_flags.executor_interacted} } else { @{source_access=$receipt.source_access;private_control_endpoint_access=$receipt.private_control_endpoint_access;real_provider_access=$receipt.real_provider_access;approval_interaction=$receipt.approval_interaction;executor_interaction=$receipt.executor_interaction} }
    foreach ($name in $flags.Keys) { if ($flags[$name] -ne $false) { throw "Receipt disallowed $name." } }
    $seen = @{}
    $seenHashes = @{}
    foreach ($number in 1..5) {
        $task = Get-Task $receipt $number
        foreach ($filename in @($task.evidence)) {
            if ([IO.Path]::GetFileName($filename) -ne $filename -or $seen.ContainsKey($filename)) { throw 'Receipt evidence filename is unsafe or duplicated.' }
            $file = Join-Path $root $filename
            if (-not (Test-Path -LiteralPath $file) -or -not $receipt.artifact_hashes.$filename -or (Get-FileSha256 $file) -ne $receipt.artifact_hashes.$filename) { throw "Receipt evidence hash failed for $filename." }
            $hash = [string]$receipt.artifact_hashes.$filename
            if ($seenHashes.ContainsKey($hash)) { throw "Receipt evidence hash is reused by task_$number and $($seenHashes[$hash])." }
            $seen[$filename] = $true
            $seenHashes[$hash] = "task_$number"
        }
    }
    $observerPath = Join-Path $root 'g-synthetic-final-observation.json'
    if ($metadata.status -eq 'G_SYNTHETIC_EVALUATOR_PASS' -and (Test-Path -LiteralPath $observerPath)) {
        $observer = Get-Content -Raw -Encoding utf8 -LiteralPath $observerPath | ConvertFrom-Json
    } else {
        $observer = Invoke-RestMethod -Uri "$($metadata.urls.backend)/_package_f/observe" -TimeoutSec 10
        $observer | ConvertTo-Json -Depth 12 | Set-Content -Encoding utf8 -LiteralPath $observerPath
    }
    $violations = @()
    foreach ($check in @(@('provider_bound_run_attempts',0),@('browser_action_mutations',0),@('browser_approval_decisions',0),@('executor_runs',0),@('fixture_seeded_action_packages',1),@('fixture_seeded_approvals',0))) { if ($observer.($check[0]) -ne $check[1]) { $violations += "$($check[0])=$($observer.($check[0]))" } }
    if ($observer.fixture.package_status -ne 'awaiting_approval') { $violations += "fixture.package_status=$($observer.fixture.package_status)" }
    if ($observer.fixture.pending_step_count -ne 1) { $violations += "fixture.pending_step_count=$($observer.fixture.pending_step_count)" }
    if ($violations.Count) { throw ('G-SYNTHETIC observer invariants failed: ' + ($violations -join ', ')) }
    if ((Get-Task $receipt 2).status -eq 'PASS' -and $observer.controlled_synthetic_sample -lt 1) { throw 'Task 2 PASS lacks the controlled synthetic sample request.' }
    if ((Get-Task $receipt 4).status -eq 'PASS' -and ($observer.controlled_409 -lt 1 -or $observer.controlled_503 -lt 1)) { throw 'Task 4 PASS lacks controlled scope/offline evidence.' }
    if ($Finalize) {
        & (Join-Path $PSScriptRoot 'stop-package-f-native-fidelity.ps1') -EvidenceRoot $root -PreserveTerminalStatus
        $metadata = Get-Content -Raw -Encoding utf8 -LiteralPath $metadataPath | ConvertFrom-Json
        if ($metadata.status -eq 'CLEANUP_INCOMPLETE') { throw 'G-SYNTHETIC cleanup did not complete.' }
        $metadata.status = 'G_SYNTHETIC_EVALUATOR_PASS'
        $metadata | Add-Member -NotePropertyName g_synthetic -NotePropertyValue @{ status='PASS'; evaluation_type='synthetic agent evaluation'; evaluator_id=$receipt.evaluator_id; source_fingerprint_sha256=$receipt.source_fingerprint_sha256; finalized_at=(Get-Date).ToString('o'); receipt_sha256=(Get-FileSha256 $receiptPath); final_observation_sha256=(Get-FileSha256 (Join-Path $root 'g-synthetic-final-observation.json')); limitation='Synthetic agent evaluation; not human usability evidence.' } -Force
        Save-Json $metadata $metadataPath
    }
    return @{ root=$root; evaluator_id=$receipt.evaluator_id; fingerprint=$receipt.source_fingerprint_sha256; receipt=$receipt; metadata=$metadata }
}

if ($PSCmdlet.ParameterSetName -eq 'Evaluator') {
    Test-EvaluatorReceipt $EvidenceRoot -Finalize | ConvertTo-Json -Depth 6
    exit 0
}

if (@($ReceiptRoots).Count -ne 5) { throw 'Aggregate requires exactly five evaluator roots.' }
$evaluators = @($ReceiptRoots | ForEach-Object { Test-EvaluatorReceipt $_ })
$ids = @($evaluators | ForEach-Object evaluator_id | Sort-Object)
if (($ids -join ',') -ne 'A01,A02,A03,A04,A05') { throw 'Aggregate requires exactly A01 through A05.' }
$fingerprints = @($evaluators | ForEach-Object fingerprint | Select-Object -Unique)
if ($fingerprints.Count -ne 1) { throw 'Evaluator receipts do not share one final source fingerprint.' }
$roots = @($evaluators | ForEach-Object root | Select-Object -Unique)
if ($roots.Count -ne 5) { throw 'Evaluator roots must be isolated.' }
$failures = @()
foreach ($number in @(1,3,5)) { if (@($evaluators | Where-Object { (Get-Task $_.receipt $number).status -eq 'PASS' }).Count -ne 5) { $failures += "task_$number requires 5/5 PASS" } }
foreach ($number in @(2,4)) { if (@($evaluators | Where-Object { (Get-Task $_.receipt $number).status -eq 'PASS' }).Count -lt 4) { $failures += "task_$number requires at least 4/5 PASS" } }
foreach ($evaluator in $evaluators) {
    foreach ($issue in @($evaluator.receipt.issues)) { if ($issue.severity -in @('Critical','Major')) { $failures += "$($evaluator.evaluator_id) has $($issue.severity) issue $($issue.id)" } }
}
$AggregateEvidenceRoot = Assert-UnderEvidenceBase $AggregateEvidenceRoot
if (-not (Test-Path -LiteralPath $AggregateEvidenceRoot)) { New-Item -ItemType Directory -Path $AggregateEvidenceRoot -Force | Out-Null }
$report = @{ schema_version=1; status=if($failures.Count){'FAIL'}else{'PASS'}; evaluation_type='synthetic agent evaluation'; limitation='Synthetic agent evaluation; not human usability evidence.'; source_fingerprint_sha256=$fingerprints[0]; evaluators=@($evaluators | ForEach-Object { @{evaluator_id=$_.evaluator_id;root=$_.root;run_id=$_.receipt.run_id;browser_profile=$_.receipt.browser_profile;tasks=$_.receipt.tasks} }); failures=$failures; finalized_at=(Get-Date).ToString('o') }
Save-Json $report (Join-Path $AggregateEvidenceRoot 'g-synthetic-aggregate-report.json')
if ($failures.Count) { throw ('G-SYNTHETIC aggregate failed: ' + ($failures -join '; ')) }
exit 0
