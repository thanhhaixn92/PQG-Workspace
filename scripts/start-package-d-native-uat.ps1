[CmdletBinding()]
param(
    [string]$EvidenceRoot,
    [int]$BackendPort = 0,
    [int]$FrontendPort = 0,
    [ValidateRange(5, 120)]
    [int]$ReadinessTimeoutSec = 30
)

# Package D native-browser support only. This script starts disposable local
# services and a synthetic fixture; it never launches or controls a browser.
# It is not a Package D PASS runner: use the paired finalizer only after the
# Browser UAT has recorded every required assertion receipt.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$evidenceBase = [System.IO.Path]::GetFullPath((Join-Path $repo 'output\playwright'))
if (-not $EvidenceRoot) { $EvidenceRoot = Join-Path $evidenceBase "package-d-native-$stamp" }
$EvidenceRoot = [System.IO.Path]::GetFullPath($EvidenceRoot)
$evidencePrefix = $evidenceBase.TrimEnd('\') + '\'
if (-not $EvidenceRoot.StartsWith($evidencePrefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'EvidenceRoot must be beneath output/playwright.' }
if (-not (Split-Path -Leaf $EvidenceRoot).StartsWith('package-d-native-', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'EvidenceRoot leaf must start with package-d-native-.' }
if (Test-Path -LiteralPath $EvidenceRoot) { throw "EvidenceRoot already exists and will not be reused: $EvidenceRoot" }

$tempRoot = Join-Path $env:TEMP "pqg-package-d-native-$stamp"
$workspaceRoot = Join-Path $tempRoot 'workspace'
$runId = [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Force -Path $EvidenceRoot, $tempRoot, $workspaceRoot | Out-Null

function Get-FreePort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    try { $listener.Start(); return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}
if ($BackendPort -eq 0) { $BackendPort = Get-FreePort }
if ($FrontendPort -eq 0) { $FrontendPort = Get-FreePort }
if ($BackendPort -eq $FrontendPort) { throw 'BackendPort and FrontendPort must differ.' }

$metadata = [ordered]@{
    schema_version = 1
    package = 'D'
    run_id = $runId
    support_route = 'native-browser-computer-use'
    status = 'STARTING'
    started_at = (Get-Date).ToString('o')
    ready_at = $null
    completed_at = $null
    evidence_root = $EvidenceRoot
    planned_assertion_count = 32
    passed_assertion_count = 0
    isolation = @{
        database = 'temporary DB_PATH beneath %TEMP%'
        workspace = 'temporary DEFAULT_WORKSPACE_ROOT beneath %TEMP%'
        ports = 'ephemeral loopback only'
        provider = 'not invoked: no turn/run endpoint is called by the fixture'
        external_network = 'not used: harness is bound to 127.0.0.1 only'
        credentials = 'not read or written'
    }
    ports = @{ backend = $BackendPort; frontend = $FrontendPort }
    urls = @{ frontend = "http://127.0.0.1:$FrontendPort"; backend = "http://127.0.0.1:$BackendPort" }
    fixture = $null
    observation_contract = @{
        snapshot = '/_package_d/observe'
        reset = '/_package_d/observe/reset'
        publish = '/_package_d/publish'
        record_assertion = '/_package_d/evidence/assertion'
        record_artifact = '/_package_d/evidence/artifact'
    }
    launch = @{}
    readiness = @{ status = 'NOT_STARTED'; timeout_seconds = $ReadinessTimeoutSec; attempts = 0 }
    browser_uat = @{ status = 'NOT_RUN'; finalized_at = $null; failure_count = $null; evidence_required = @('desktop-sidebar-workhub-a1.jpg', 'desktop-sidebar-workhub-a2-late.jpg', 'desktop-sidebar-workhub-a2-error.jpg', 'desktop-sidebar-workhub-b1-active.jpg', 'desktop-sidebar-workhub-b1-done.jpg', 'mobile-sidebar-workhub-a1.jpg', 'mobile-sidebar-workhub-a2-late.jpg', 'mobile-sidebar-workhub-a2-error.jpg', 'mobile-sidebar-workhub-b1-active.jpg', 'mobile-sidebar-workhub-b1-done.jpg', 'browser-console-redacted.json', 'browser-network-redacted.json') }
    cleanup = $null
}
function Save-Metadata { $metadata | ConvertTo-Json -Depth 16 | Set-Content -Encoding utf8 -LiteralPath (Join-Path $EvidenceRoot 'run-metadata.json') }
function Set-ProcessMetadata([string]$Name, $Process) {
    if (-not $Process) { return }
    $Process.Refresh()
    $entry = $metadata.launch[$Name]
    $entry.pid = $Process.Id
    $entry.start_time = $Process.StartTime.ToString('o')
    $entry.exited = $Process.HasExited
    if ($Process.HasExited) { $entry.exit_code = $Process.ExitCode }
}
function Set-ListenerMetadata([string]$Name) {
    $port = [int]$metadata.ports[$Name]
    $listener = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $listener.Count) { return $false }
    $process = Get-Process -Id $listener[0].OwningProcess -ErrorAction Stop
    $entry = $metadata.launch[$Name]
    $entry.listener_pid = $process.Id
    $entry.listener_start_time = $process.StartTime.ToString('o')
    return $true
}
function Stop-RecordedProcess([string]$Name, $Process) {
    if (-not $Process) { return }
    $Process.Refresh()
    if (-not $Process.HasExited) { Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue }
    $Process.WaitForExit(5000) | Out-Null
    Set-ProcessMetadata $Name $Process
}
function Test-ProcessAlive([string]$Name, $Process) {
    if (-not $Process) { throw "$Name process was not started." }
    $Process.Refresh(); Set-ProcessMetadata $Name $Process
    if ($Process.HasExited) { throw "$Name exited before readiness; retained logs: $($metadata.launch[$Name].stdout_log), $($metadata.launch[$Name].stderr_log)" }
}
function Invoke-LocalApi([string]$Method, [string]$Path, $Body = $null) {
    $params = @{ Uri = "http://127.0.0.1:$BackendPort$Path"; Method = $Method; ContentType = 'application/json'; TimeoutSec = 15 }
    if ($null -ne $Body) { $params.Body = $Body | ConvertTo-Json -Depth 12 -Compress }
    Invoke-RestMethod @params
}
function Wait-Ready {
    $deadline = (Get-Date).AddSeconds($ReadinessTimeoutSec)
    $metadata.readiness.status = 'WAITING'
    while ((Get-Date) -lt $deadline) {
        $metadata.readiness.attempts++
        [void](Set-ListenerMetadata 'backend')
        [void](Set-ListenerMetadata 'frontend')
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSec 2
            $page = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -UseBasicParsing -TimeoutSec 2
            if ($health.status -eq 'ok' -and $page.StatusCode -eq 200) {
                [void](Set-ListenerMetadata 'backend')
                [void](Set-ListenerMetadata 'frontend')
                $metadata.readiness.status = 'READY'; Save-Metadata; return
            }
        } catch { }
        Start-Sleep -Milliseconds 250
    }
    throw "Temporary Package D native services did not become ready within $ReadinessTimeoutSec seconds."
}

# The harness is process-local and loopback-only. Its non-product endpoints
# observe requests, control synthetic events, and write redacted evidence.
$harnessPath = Join-Path $tempRoot 'package_d_native_harness.py'
@'
import base64, hashlib, json, os, re, time, uuid
from pathlib import Path
import aiosqlite
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from app.main import create_app
from app.services.event_bus import event_bus
from app.api.schemas import SseDoneEvent, SseErrorEvent, SseTokenEvent

app = create_app()
stream_re = re.compile(r"^/api/assistant/threads/([^/]+)/stream$")
observations = {"stream_subscriptions": {}, "stream_open_total": {}, "product_post_paths": {}}
expected_threads = {}
expected_turns = {}

def db_path(): return os.environ['DB_PATH']
def evidence_path(): return Path(os.environ['PACKAGE_D_EVIDENCE_ROOT'])
ALLOWED_ARTIFACTS = {
    'desktop-sidebar-workhub-a1.jpg', 'desktop-sidebar-workhub-b1-active.jpg', 'desktop-sidebar-workhub-b1-done.jpg',
    'desktop-sidebar-workhub-a2-late.jpg', 'desktop-sidebar-workhub-a2-error.jpg',
    'mobile-sidebar-workhub-a1.jpg', 'mobile-sidebar-workhub-b1-active.jpg', 'mobile-sidebar-workhub-b1-done.jpg',
    'mobile-sidebar-workhub-a2-late.jpg', 'mobile-sidebar-workhub-a2-error.jpg',
    'browser-console-redacted.json', 'browser-network-redacted.json',
}
def synthetic(value: str):
    if value and not value.startswith('PACKAGE-D-'):
        raise HTTPException(status_code=422, detail='Package D fixture values must be synthetic.')

@app.middleware('http')
async def observe_product_requests(request: Request, call_next):
    path = request.url.path
    match = stream_re.match(path)
    thread_id = None
    if request.method == 'GET' and match:
        thread_id = match.group(1)
        observations['stream_subscriptions'][thread_id] = observations['stream_subscriptions'].get(thread_id, 0) + 1
        observations['stream_open_total'][thread_id] = observations['stream_open_total'].get(thread_id, 0) + 1
    if request.method == 'POST' and path.startswith('/api/'):
        observations['product_post_paths'][path] = observations['product_post_paths'].get(path, 0) + 1
    try:
        response = await call_next(request)
    except Exception:
        if thread_id:
            remaining = observations['stream_subscriptions'].get(thread_id, 1) - 1
            if remaining > 0: observations['stream_subscriptions'][thread_id] = remaining
            else: observations['stream_subscriptions'].pop(thread_id, None)
        raise
    if thread_id:
        original_iterator = response.body_iterator
        async def tracked_iterator():
            try:
                async for chunk in original_iterator:
                    yield chunk
            finally:
                remaining = observations['stream_subscriptions'].get(thread_id, 1) - 1
                if remaining > 0: observations['stream_subscriptions'][thread_id] = remaining
                else: observations['stream_subscriptions'].pop(thread_id, None)
        response.body_iterator = tracked_iterator()
    return response

class SeedTurn(BaseModel):
    thread_id: str
    work_id: str
    conversation_id: str
    marker: str

class Publish(BaseModel):
    thread_id: str
    turn_id: str
    event: str
    text: str = ''

class ConfigureObservation(BaseModel):
    thread_a1: str
    thread_b1: str
    desktop_b1: str
    mobile_b1: str

class AssertionReceipt(BaseModel):
    assertion_id: str = Field(pattern=r'^D-(?:desktop|mobile)-(?:0[1-9]|1[0-5])$|^D-global-0[12]$')
    status: str = Field(pattern=r'^(PASS|FAIL)$')
    run_id: str = Field(min_length=32, max_length=32)
    viewport: str = Field(pattern=r'^(desktop|mobile|global)$')
    evidence: list[str] = Field(min_length=1, max_length=4)
    artifact_hashes: dict[str, str] = Field(min_length=1)

class EvidenceArtifact(BaseModel):
    run_id: str = Field(min_length=32, max_length=32)
    filename: str = Field(pattern=r'^(?:desktop|mobile)-sidebar-workhub-(?:a1|a2-late|a2-error|b1-active|b1-done)\.jpg$|^browser-(?:console|network)-redacted\.json$')
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    data_base64: str = Field(min_length=1)

def assertion_viewport(assertion_id: str) -> str:
    return assertion_id.split('-')[1]

def required_artifacts_for(assertion_id: str) -> set[str]:
    viewport = assertion_viewport(assertion_id)
    if viewport == 'global':
        return {'browser-network-redacted.json'}
    sequence = int(assertion_id.rsplit('-', 1)[1])
    if sequence <= 6:
        return {f'{viewport}-sidebar-workhub-a1.jpg'}
    if sequence <= 9:
        return {f'{viewport}-sidebar-workhub-a2-late.jpg'}
    if sequence == 10:
        return {f'{viewport}-sidebar-workhub-a2-error.jpg'}
    if sequence <= 13:
        return {f'{viewport}-sidebar-workhub-b1-active.jpg'}
    if sequence == 14:
        return {f'{viewport}-sidebar-workhub-b1-done.jpg'}
    return {'browser-console-redacted.json', 'browser-network-redacted.json'}

def validate_diagnostic_artifact(filename: str, data: bytes):
    try:
        document = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=422, detail='Diagnostic artifact is not UTF-8 JSON') from error
    if not isinstance(document, dict):
        raise HTTPException(status_code=422, detail='Diagnostic artifact must be a JSON object')
    if filename == 'browser-console-redacted.json':
        entries = document.get('entries')
        if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
            raise HTTPException(status_code=422, detail='Console artifact must contain an entries array')
        if any(str(entry.get('level', '')).lower() in {'error', 'fatal'} for entry in entries):
            raise HTTPException(status_code=422, detail='Console artifact contains an error-level entry')
    if filename == 'browser-network-redacted.json':
        requests = document.get('requests')
        if not isinstance(requests, list) or any(not isinstance(entry, dict) or not isinstance(entry.get('url'), str) for entry in requests):
            raise HTTPException(status_code=422, detail='Network artifact must contain requests with URLs')
        if any(not entry['url'].startswith(('http://127.0.0.1:', 'http://localhost:')) for entry in requests):
            raise HTTPException(status_code=422, detail='Network artifact contains a non-loopback URL')

def validate_jpeg_artifact(data: bytes):
    if len(data) < 16 or not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
        raise HTTPException(status_code=422, detail='Screenshot artifact is not a complete JPEG')
    offset, saw_frame, saw_scan = 2, False, False
    while offset + 4 <= len(data) - 2:
        if data[offset] != 0xff: break
        marker = data[offset + 1]
        if marker == 0xda:
            saw_scan = True
            break
        if marker in {0xd8, 0xd9}:
            offset += 2
            continue
        length = int.from_bytes(data[offset + 2:offset + 4], 'big')
        if length < 2 or offset + 2 + length > len(data): break
        if marker in {0xc0, 0xc1, 0xc2}:
            segment = data[offset + 4:offset + 2 + length]
            if len(segment) < 5 or int.from_bytes(segment[1:3], 'big') < 1 or int.from_bytes(segment[3:5], 'big') < 1:
                raise HTTPException(status_code=422, detail='Screenshot JPEG has invalid dimensions')
            saw_frame = True
        offset += 2 + length
    if not (saw_frame and saw_scan):
        raise HTTPException(status_code=422, detail='Screenshot JPEG is incomplete')

@app.post('/_package_d/seed-turn')
async def seed_turn(request: SeedTurn):
    synthetic(request.marker)
    turn_id, now = 'package-d-turn-' + uuid.uuid4().hex, int(time.time())
    async with aiosqlite.connect(db_path()) as conn:
        await conn.execute("INSERT INTO assistant_turns (id, thread_id, work_id, conversation_id, role, status, model_id, created_at) VALUES (?, ?, ?, ?, 'assistant', 'running', 'package-d-synthetic', ?)", (turn_id, request.thread_id, request.work_id, request.conversation_id, now))
        await conn.execute("INSERT INTO assistant_turn_parts (id, turn_id, part_type, content_json, sort_order, created_at) VALUES (?, ?, 'text', ?, 0, ?)", (uuid.uuid4().hex, turn_id, json.dumps({'text': request.marker}), now))
        await conn.commit()
    return {'turn_id': turn_id}

@app.post('/_package_d/observe/configure')
async def configure_observation(config: ConfigureObservation):
    expected_threads.update({'a1': config.thread_a1, 'b1': config.thread_b1})
    expected_turns.update({'desktop': config.desktop_b1, 'mobile': config.mobile_b1})
    return {'configured': True}

@app.post('/_package_d/publish')
async def publish(request: Publish):
    synthetic(request.text)
    if request.event == 'token':
        await event_bus.publish('assistant:' + request.thread_id, SseTokenEvent(text=request.text, assistant_turn_id=request.turn_id, thread_id=request.thread_id))
        return {'published': 'token'}
    if request.event not in {'done', 'error'}:
        raise HTTPException(status_code=400, detail='Unsupported synthetic event')
    now, status = int(time.time()), ('completed' if request.event == 'done' else 'failed')
    message = request.text or 'PACKAGE-D-SYNTHETIC-TERMINAL'
    async with aiosqlite.connect(db_path()) as conn:
        changed = await conn.execute("UPDATE assistant_turns SET status = ?, completed_at = ?, error = ? WHERE id = ? AND status = 'running'", (status, now, message if status == 'failed' else None, request.turn_id))
        if changed.rowcount != 1: raise HTTPException(status_code=409, detail='Synthetic turn is not running')
        await conn.commit()
    event = SseDoneEvent(assistant_turn_id=request.turn_id, thread_id=request.thread_id) if request.event == 'done' else SseErrorEvent(message=message, assistant_turn_id=request.turn_id, thread_id=request.thread_id)
    await event_bus.publish('assistant:' + request.thread_id, event)
    return {'published': request.event}

async def inspection():
    result = {
        'stream_subscriptions': dict(sorted(observations['stream_subscriptions'].items())),
        'stream_open_total': dict(sorted(observations['stream_open_total'].items())),
        'product_post_paths': dict(sorted(observations['product_post_paths'].items())),
        'action_packages': 0, 'approvals': 0, 'synthetic_turns': 0,
    }
    async with aiosqlite.connect(db_path()) as conn:
        async with conn.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur: tables = {row[0] for row in await cur.fetchall()}
        if 'action_packages' in tables:
            async with conn.execute('SELECT COUNT(*) FROM action_packages') as cur: result['action_packages'] = (await cur.fetchone())[0]
        for table in ('approval_requests', 'approvals'):
            if table in tables:
                async with conn.execute(f'SELECT COUNT(*) FROM {table}') as cur: result['approvals'] += (await cur.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM assistant_turns WHERE model_id='package-d-synthetic'") as cur: result['synthetic_turns'] = (await cur.fetchone())[0]
    return result

@app.get('/_package_d/observe')
async def observe(): return await inspection()

@app.post('/_package_d/observe/reset')
async def reset_observation():
    observations['stream_open_total'].clear(); observations['product_post_paths'].clear()
    return {'reset': True}

@app.post('/_package_d/evidence/assertion')
async def record_assertion(receipt: AssertionReceipt):
    if receipt.run_id != os.environ['PACKAGE_D_RUN_ID']:
        raise HTTPException(status_code=409, detail='Package D run identity mismatch')
    if receipt.viewport != assertion_viewport(receipt.assertion_id):
        raise HTTPException(status_code=422, detail='Receipt viewport does not match assertion id')
    expected_artifacts = required_artifacts_for(receipt.assertion_id)
    if not expected_artifacts.issubset(set(receipt.evidence)):
        raise HTTPException(status_code=422, detail='Receipt is missing its assertion-specific Browser artifact')
    for filename in receipt.evidence:
        if filename not in ALLOWED_ARTIFACTS:
            raise HTTPException(status_code=422, detail='Receipt references an unapproved artifact name')
        if receipt.artifact_hashes.get(filename) is None or not re.fullmatch(r'[0-9a-f]{64}', receipt.artifact_hashes[filename]):
            raise HTTPException(status_code=422, detail='Receipt evidence hash is missing or invalid')
    observed_streams = None
    if receipt.assertion_id.endswith('-06') or receipt.assertion_id.endswith('-13'):
        key = 'a1' if receipt.assertion_id.endswith('-06') else 'b1'
        expected_thread = expected_threads.get(key)
        if not expected_thread or observations['stream_subscriptions'] != {expected_thread: 1}:
            raise HTTPException(status_code=422, detail='Observed SSE subscription count is not exactly one for the asserted thread')
        observed_streams = dict(observations['stream_subscriptions'])
    observed_turn_status = None
    if receipt.assertion_id.endswith('-14'):
        expected_turn = expected_turns.get(receipt.viewport)
        if not expected_turn:
            raise HTTPException(status_code=422, detail='Expected terminal turn is not configured')
        async with aiosqlite.connect(db_path()) as conn:
            async with conn.execute('SELECT status FROM assistant_turns WHERE id = ?', (expected_turn,)) as cur:
                row = await cur.fetchone()
        observed_turn_status = row[0] if row else None
        if observed_turn_status != 'completed':
            raise HTTPException(status_code=422, detail='Asserted B1 turn is not completed')
    payload = {'at': int(time.time()), 'assertion_id': receipt.assertion_id, 'status': receipt.status, 'run_id': receipt.run_id, 'viewport': receipt.viewport, 'evidence': receipt.evidence, 'artifact_hashes': receipt.artifact_hashes, 'observed_stream_subscriptions': observed_streams, 'observed_turn_status': observed_turn_status}
    with (evidence_path() / 'native-assertion-receipts.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + '\n')
    return {'recorded': receipt.assertion_id, 'status': receipt.status}

@app.post('/_package_d/evidence/artifact')
async def record_artifact(artifact: EvidenceArtifact):
    if artifact.run_id != os.environ['PACKAGE_D_RUN_ID']:
        raise HTTPException(status_code=409, detail='Package D run identity mismatch')
    try:
        data = base64.b64decode(artifact.data_base64, validate=True)
    except ValueError as error:
        raise HTTPException(status_code=422, detail='Artifact is not valid base64') from error
    if hashlib.sha256(data).hexdigest() != artifact.sha256:
        raise HTTPException(status_code=422, detail='Artifact SHA-256 mismatch')
    if artifact.filename not in ALLOWED_ARTIFACTS:
        raise HTTPException(status_code=422, detail='Artifact name is not approved')
    if artifact.filename.endswith('.jpg'):
        validate_jpeg_artifact(data)
    else:
        validate_diagnostic_artifact(artifact.filename, data)
    target = evidence_path() / artifact.filename
    if target.exists():
        raise HTTPException(status_code=409, detail='Artifact filename is immutable for this run')
    target.write_bytes(data)
    record = {'at': int(time.time()), 'run_id': artifact.run_id, 'filename': artifact.filename, 'sha256': artifact.sha256, 'byte_count': len(data)}
    with (evidence_path() / 'native-artifact-manifest.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
    return {'stored': artifact.filename, 'sha256': artifact.sha256}
'@ | Set-Content -Encoding utf8 -LiteralPath $harnessPath

$launcherPath = Join-Path $tempRoot 'package_d_native_vite_launcher.mjs'
@'
import { pathToFileURL } from 'node:url';
const [frontendRoot, backendPort, frontendPort, viteModulePath, reactPluginPath] = process.argv.slice(2);
const { createServer } = await import(pathToFileURL(viteModulePath).href);
const reactModule = await import(pathToFileURL(reactPluginPath).href);
const target = `http://127.0.0.1:${backendPort}`;
const server = await createServer({
  root: frontendRoot,
  configFile: false,
  plugins: [reactModule.default()],
  server: {
    host: '127.0.0.1', port: Number(frontendPort), strictPort: true,
    proxy: { '/api/health': { target, rewrite: path => path.replace(/^\/api/, '') }, '/api': target },
  },
});
await server.listen();
server.printUrls();
const close = async () => { await server.close(); process.exit(0); };
process.once('SIGINT', close); process.once('SIGTERM', close);
'@ | Set-Content -Encoding utf8 -LiteralPath $launcherPath

$manifest = [ordered]@{
    schema_version = 1
    package = 'D'
    route = 'native-browser-computer-use'
    planned_assertion_count = 32
    run_id = $runId
    browser_javascript_injection = 'prohibited'
    recording_endpoint = '/_package_d/evidence/assertion'
    assertions = @(
        @{ id='D-desktop-01'; expected='Sidebar is visible.' },
        @{ id='D-desktop-02'; expected='WorkHub is visible.' },
        @{ id='D-desktop-03'; expected='Work A is selected in WorkHub.' },
        @{ id='D-desktop-04'; expected='Conversation A1 is selected in WorkHub.' },
        @{ id='D-desktop-05'; expected='Sidebar selects Work A and A1.' },
        @{ id='D-desktop-06'; expected='Observation reports exactly one A1 stream subscription.' },
        @{ id='D-desktop-07'; expected='Changing Sidebar to A2 leaves WorkHub at A1.' },
        @{ id='D-desktop-08'; expected='Controlled A1 late token is visible in unchanged WorkHub A1.' },
        @{ id='D-desktop-09'; expected='Controlled A1 late token is absent from Sidebar A2.' },
        @{ id='D-desktop-10'; expected='A1 error terminal is visible and its persisted marker remains.' },
        @{ id='D-desktop-11'; expected='Work B is selected in WorkHub.' },
        @{ id='D-desktop-12'; expected='Conversation B1 is selected in WorkHub and Sidebar.' },
        @{ id='D-desktop-13'; expected='Observation reports exactly one B1 stream subscription.' },
        @{ id='D-desktop-14'; expected='B1 done terminal preserves its persisted marker.' },
        @{ id='D-desktop-15'; expected='Visible DevTools Console has no error and Network has only loopback origins.' },
        @{ id='D-mobile-01'; expected='Sidebar is visible at mobile viewport.' },
        @{ id='D-mobile-02'; expected='WorkHub is visible at mobile viewport.' },
        @{ id='D-mobile-03'; expected='Work A is selected in WorkHub.' },
        @{ id='D-mobile-04'; expected='Conversation A1 is selected in WorkHub.' },
        @{ id='D-mobile-05'; expected='Sidebar selects Work A and A1.' },
        @{ id='D-mobile-06'; expected='Observation reports exactly one A1 stream subscription for this viewport.' },
        @{ id='D-mobile-07'; expected='Changing Sidebar to A2 leaves WorkHub at A1.' },
        @{ id='D-mobile-08'; expected='Controlled A1 late token is visible in unchanged WorkHub A1.' },
        @{ id='D-mobile-09'; expected='Controlled A1 late token is absent from Sidebar A2.' },
        @{ id='D-mobile-10'; expected='A1 error terminal is visible and its persisted marker remains.' },
        @{ id='D-mobile-11'; expected='Work B is selected in WorkHub.' },
        @{ id='D-mobile-12'; expected='Conversation B1 is selected in WorkHub and Sidebar.' },
        @{ id='D-mobile-13'; expected='Observation reports exactly one B1 stream subscription for this viewport.' },
        @{ id='D-mobile-14'; expected='B1 done terminal preserves its persisted marker.' },
        @{ id='D-mobile-15'; expected='Visible DevTools Console has no error and Network has only loopback origins.' },
        @{ id='D-global-01'; expected='Observation product_post_paths is empty after reset.' },
        @{ id='D-global-02'; expected='Observation has zero Action Packages and approvals, and four synthetic turns.' }
    )
}

$backend = $null
$frontend = $null
Save-Metadata
try {
    $env:DB_PATH = Join-Path $tempRoot 'app.db'
    $env:DEFAULT_WORKSPACE_ROOT = $workspaceRoot
    $env:CORS_ORIGINS = "http://127.0.0.1:$FrontendPort"
    $env:OUTBOX_DISPATCHER_ENABLED = '0'
    $env:HERMES_DEV_MOCK = '0'
    $env:PACKAGE_D_EVIDENCE_ROOT = $EvidenceRoot
    $env:PACKAGE_D_RUN_ID = $runId
    $backendExe = Join-Path $repo 'backend\.venv\Scripts\python.exe'
    $viteModule = Join-Path $repo 'frontend\node_modules\vite\dist\node\index.js'
    $reactPlugin = Join-Path $repo 'frontend\node_modules\@vitejs\plugin-react\dist\index.js'
    $frontendRoot = Join-Path $repo 'frontend'
    foreach ($requiredPath in @($backendExe, $viteModule, $reactPlugin)) {
        if (-not (Test-Path -LiteralPath $requiredPath)) { throw "Required installed local tooling is unavailable: $requiredPath. No package installation was attempted." }
    }
    $backendArgs = @('-m', 'uvicorn', 'package_d_native_harness:app', '--app-dir', $tempRoot, '--host', '127.0.0.1', '--port', "$BackendPort")
    $frontendArgs = @($launcherPath, $frontendRoot, "$BackendPort", "$FrontendPort", $viteModule, $reactPlugin)
    $metadata.launch.backend = @{ command = 'python -m uvicorn package_d_native_harness:app --host 127.0.0.1'; listener_command_fragment = 'package_d_native_harness:app'; stdout_log = (Join-Path $EvidenceRoot 'backend.stdout.log'); stderr_log = (Join-Path $EvidenceRoot 'backend.stderr.log') }
    $metadata.launch.frontend = @{ command = 'node package_d_native_vite_launcher.mjs (Vite configFile=false)'; listener_command_fragment = 'package_d_native_vite_launcher.mjs'; stdout_log = (Join-Path $EvidenceRoot 'frontend.stdout.log'); stderr_log = (Join-Path $EvidenceRoot 'frontend.stderr.log') }
    Save-Metadata
    $backend = Start-Process -FilePath $backendExe -ArgumentList $backendArgs -WorkingDirectory (Join-Path $repo 'backend') -WindowStyle Hidden -RedirectStandardOutput $metadata.launch.backend.stdout_log -RedirectStandardError $metadata.launch.backend.stderr_log -PassThru
    Set-ProcessMetadata 'backend' $backend; Save-Metadata
    $frontend = Start-Process -FilePath 'node.exe' -ArgumentList $frontendArgs -WorkingDirectory $frontendRoot -WindowStyle Hidden -RedirectStandardOutput $metadata.launch.frontend.stdout_log -RedirectStandardError $metadata.launch.frontend.stderr_log -PassThru
    Set-ProcessMetadata 'frontend' $frontend; Save-Metadata
    Wait-Ready

    $workA = Invoke-LocalApi 'Post' '/api/sessions' @{ title='PACKAGE-D-WORK-A'; goal='synthetic native browser UAT'; data_scope='work_only' }
    $workB = Invoke-LocalApi 'Post' '/api/sessions' @{ title='PACKAGE-D-WORK-B'; goal='synthetic native browser UAT'; data_scope='work_only' }
    $convA1 = @(Invoke-LocalApi 'Get' "/api/works/$($workA.id)/conversations")[0]
    $convB1 = @(Invoke-LocalApi 'Get' "/api/works/$($workB.id)/conversations")[0]
    $convA1 = Invoke-LocalApi 'Patch' "/api/works/$($workA.id)/conversations/$($convA1.id)" @{ title='PACKAGE-D-CONV-A1'; purpose='Synthetic isolated native UAT fixture' }
    $convB1 = Invoke-LocalApi 'Patch' "/api/works/$($workB.id)/conversations/$($convB1.id)" @{ title='PACKAGE-D-CONV-B1'; purpose='Synthetic isolated native UAT fixture' }
    $convA2 = Invoke-LocalApi 'Post' "/api/works/$($workA.id)/conversations" @{ title='PACKAGE-D-CONV-A2'; purpose='Synthetic native scope-switch target' }
    $threadA1 = Invoke-LocalApi 'Post' "/api/assistant/works/$($workA.id)/conversations/$($convA1.id)/assistant-thread"
    $threadB1 = Invoke-LocalApi 'Post' "/api/assistant/works/$($workB.id)/conversations/$($convB1.id)/assistant-thread"
    $turns = @{}
    foreach ($viewport in @('desktop', 'mobile')) {
        $turnA = Invoke-LocalApi 'Post' '/_package_d/seed-turn' @{ thread_id=$threadA1.id; work_id=$workA.id; conversation_id=$convA1.id; marker="PACKAGE-D-PERSISTED-A-$viewport" }
        $turnB = Invoke-LocalApi 'Post' '/_package_d/seed-turn' @{ thread_id=$threadB1.id; work_id=$workB.id; conversation_id=$convB1.id; marker="PACKAGE-D-PERSISTED-B-$viewport" }
        $turns[$viewport] = @{ a1=@{ id=$turnA.turn_id; marker="PACKAGE-D-PERSISTED-A-$viewport"; late_token="PACKAGE-D-LATE-A1-$viewport"; error="PACKAGE-D-SYNTHETIC-ERROR-$viewport" }; b1=@{ id=$turnB.turn_id; marker="PACKAGE-D-PERSISTED-B-$viewport" } }
    }
    $metadata.fixture = @{ workA=@{id=$workA.id; title=$workA.title}; workB=@{id=$workB.id; title=$workB.title}; convA1=@{id=$convA1.id; title=$convA1.title}; convA2=@{id=$convA2.id; title=$convA2.title}; convB1=@{id=$convB1.id; title=$convB1.title}; threadA1=@{id=$threadA1.id}; threadB1=@{id=$threadB1.id}; turns=$turns }
    Invoke-LocalApi 'Post' '/_package_d/observe/configure' @{ thread_a1=$threadA1.id; thread_b1=$threadB1.id; desktop_b1=$turns.desktop.b1.id; mobile_b1=$turns.mobile.b1.id } | Out-Null
    Invoke-LocalApi 'Post' '/_package_d/observe/reset' | Out-Null
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 -LiteralPath (Join-Path $EvidenceRoot 'native-uat-manifest.json')
    $metadata.status = 'AWAITING_BROWSER_UAT'; $metadata.ready_at = (Get-Date).ToString('o'); Save-Metadata
    Write-Output $EvidenceRoot
} catch {
    $metadata.status = 'FAIL'; $metadata.completed_at = (Get-Date).ToString('o'); $metadata.failure = @{ stage='starter'; message=$_.Exception.Message }
    $captureDeadline = (Get-Date).AddSeconds(2)
    do {
        [void](Set-ListenerMetadata 'backend')
        [void](Set-ListenerMetadata 'frontend')
        if (-not $metadata.launch.backend.listener_pid -or -not $metadata.launch.frontend.listener_pid) { Start-Sleep -Milliseconds 100 }
    } while ((Get-Date) -lt $captureDeadline -and (-not $metadata.launch.backend.listener_pid -or -not $metadata.launch.frontend.listener_pid))
    Save-Metadata
    try {
        & (Join-Path $PSScriptRoot 'stop-package-d-native-uat.ps1') -EvidenceRoot $EvidenceRoot -PreserveTerminalStatus
        if (-not $?) { throw 'Verified Package D cleanup returned a failure status.' }
    } catch {
        $metadata = Get-Content -Raw -Encoding utf8 -LiteralPath (Join-Path $EvidenceRoot 'run-metadata.json') | ConvertFrom-Json
        $metadata.status = 'CLEANUP_INCOMPLETE'
        $metadata.completed_at = (Get-Date).ToString('o')
        $metadata | ConvertTo-Json -Depth 16 | Set-Content -Encoding utf8 -LiteralPath (Join-Path $EvidenceRoot 'run-metadata.json')
    }
    throw
}
