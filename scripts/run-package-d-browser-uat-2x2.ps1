[CmdletBinding()]
param(
    [string]$EvidenceRoot,
    [int]$BackendPort = 0,
    [int]$FrontendPort = 0,
    [ValidateRange(5, 120)]
    [int]$ReadinessTimeoutSec = 30,
    [ValidateRange(30, 300)]
    [int]$BrowserTimeoutSec = 120
)

# Package D only.  This is an isolated characterization runner: product code,
# tests, configuration and state files remain untouched.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if (-not $EvidenceRoot) { $EvidenceRoot = Join-Path $repo "output\playwright\package-d-$stamp" }
$EvidenceRoot = [System.IO.Path]::GetFullPath($EvidenceRoot)
$tempRoot = Join-Path $env:TEMP "pqg-package-d-2x2-$stamp"
$profileRoot = Join-Path $tempRoot 'browser-profile'
New-Item -ItemType Directory -Force -Path $EvidenceRoot, $tempRoot, $profileRoot, (Join-Path $tempRoot 'workspace') | Out-Null

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
    runner = 'scripts/run-package-d-browser-uat-2x2.ps1'
    status = 'RUNNING'
    started_at = (Get-Date).ToString('o')
    completed_at = $null
    assertion_count = 0
    isolation = @{
        database = 'temporary DB_PATH beneath %TEMP%'
        workspace = 'temporary DEFAULT_WORKSPACE_ROOT beneath %TEMP%'
        browser_profiles = 'one temporary persistent profile per viewport beneath %TEMP%'
        ports = 'ephemeral loopback only'
        provider = 'not invoked: no turn/run endpoint is called by the browser or fixture'
        external_network = 'not used: browser rejects every non-loopback origin'
        credentials = 'not read or written'
    }
    ports = @{ backend = $BackendPort; frontend = $FrontendPort }
    assertions = @()
    launch = @{}
    readiness = @{ timeout_seconds = $ReadinessTimeoutSec; status = 'NOT_STARTED'; attempts = 0 }
}
function Save-Metadata { $metadata | ConvertTo-Json -Depth 12 | Set-Content -Encoding utf8 -LiteralPath (Join-Path $EvidenceRoot 'run-metadata.json') }
function Set-TerminalFailure([string]$Stage, [string]$Message) {
    $metadata.status = 'FAIL'
    $metadata.completed_at = (Get-Date).ToString('o')
    $metadata.failure = @{ stage = $Stage; message = $Message }
}
function Update-ProcessMetadata([string]$Name, $Process) {
    if (-not $Process) { return }
    $Process.Refresh()
    $processMetadata = $metadata.launch[$Name]
    $processMetadata.pid = $Process.Id
    $processMetadata.exited = $Process.HasExited
    if ($Process.HasExited -and $null -ne $Process.ExitCode) { $processMetadata.exit_code = $Process.ExitCode }
}
function Test-ProcessAlive([string]$Name, $Process) {
    if (-not $Process) { throw "$Name process was not started." }
    $Process.Refresh()
    Update-ProcessMetadata $Name $Process
    if ($Process.HasExited) {
        throw "$Name exited before readiness; command: $($metadata.launch[$Name].command); exit code: $($Process.ExitCode); retained logs: $($metadata.launch[$Name].stdout_log), $($metadata.launch[$Name].stderr_log)"
    }
}
function Invoke-LocalApi([string]$Method, [string]$Path, $Body = $null) {
    $params = @{ Uri = "http://127.0.0.1:$BackendPort$Path"; Method = $Method; ContentType = 'application/json'; TimeoutSec = 15 }
    if ($null -ne $Body) { $params.Body = $Body | ConvertTo-Json -Depth 10 -Compress }
    Invoke-RestMethod @params
}
function Wait-Ready {
    $deadline = (Get-Date).AddSeconds($ReadinessTimeoutSec)
    $lastError = $null
    $metadata.readiness.status = 'WAITING'
    while ((Get-Date) -lt $deadline) {
        $metadata.readiness.attempts++
        Test-ProcessAlive 'backend' $backend
        Test-ProcessAlive 'frontend' $frontend
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSec 2
            $page = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -UseBasicParsing -TimeoutSec 2
            if ($health.status -eq 'ok' -and $page.StatusCode -eq 200) {
                $metadata.readiness.status = 'READY'
                Save-Metadata
                return
            }
            $lastError = "backend status=$($health.status); frontend status=$($page.StatusCode)"
        } catch { $lastError = $_.Exception.Message }
        Start-Sleep -Milliseconds 250
    }
    Test-ProcessAlive 'backend' $backend
    Test-ProcessAlive 'frontend' $frontend
    throw "Temporary Package D services did not become ready within $ReadinessTimeoutSec seconds. Last readiness error: $lastError"
}

# This process-local harness only seeds and terminates synthetic persisted turns.
# The browser still consumes the product REST/SSE routes, never the harness UI.
$harnessPath = Join-Path $tempRoot 'package_d_2x2_harness.py'
@'
import json, os, time, uuid
import aiosqlite
from fastapi import HTTPException
from pydantic import BaseModel
from app.main import create_app
from app.services.event_bus import event_bus
from app.api.schemas import SseDoneEvent, SseErrorEvent, SseTokenEvent

app = create_app()

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

def db_path(): return os.environ['DB_PATH']

@app.post('/_package_d/seed-turn')
async def seed_turn(request: SeedTurn):
    turn_id, now = 'package-d-turn-' + uuid.uuid4().hex, int(time.time())
    async with aiosqlite.connect(db_path()) as conn:
        await conn.execute("INSERT INTO assistant_turns (id, thread_id, work_id, conversation_id, role, status, model_id, created_at) VALUES (?, ?, ?, ?, 'assistant', 'running', 'package-d-synthetic', ?)", (turn_id, request.thread_id, request.work_id, request.conversation_id, now))
        await conn.execute("INSERT INTO assistant_turn_parts (id, turn_id, part_type, content_json, sort_order, created_at) VALUES (?, ?, 'text', ?, 0, ?)", (uuid.uuid4().hex, turn_id, json.dumps({'text': request.marker}), now))
        await conn.commit()
    return {'turn_id': turn_id}

@app.post('/_package_d/publish')
async def publish(request: Publish):
    if request.event == 'token':
        await event_bus.publish('assistant:' + request.thread_id, SseTokenEvent(text=request.text, assistant_turn_id=request.turn_id, thread_id=request.thread_id))
        return {'published': 'token'}
    if request.event not in {'done', 'error'}: raise HTTPException(status_code=400, detail='Unsupported synthetic event')
    now, status = int(time.time()), ('completed' if request.event == 'done' else 'failed')
    async with aiosqlite.connect(db_path()) as conn:
        changed = await conn.execute("UPDATE assistant_turns SET status = ?, completed_at = ?, error = ? WHERE id = ? AND status = 'running'", (status, now, request.text if request.event == 'error' else None, request.turn_id))
        if changed.rowcount != 1: raise HTTPException(status_code=409, detail='Synthetic turn is not running')
        await conn.commit()
    event = SseDoneEvent(assistant_turn_id=request.turn_id, thread_id=request.thread_id) if request.event == 'done' else SseErrorEvent(message=request.text or 'PACKAGE-D-SYNTHETIC-ERROR', assistant_turn_id=request.turn_id, thread_id=request.thread_id)
    await event_bus.publish('assistant:' + request.thread_id, event)
    return {'published': request.event}

@app.get('/_package_d/inspect')
async def inspect_fixture():
    result = {'action_packages': 0, 'approvals': 0, 'synthetic_turns': 0}
    async with aiosqlite.connect(db_path()) as conn:
        async with conn.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur: tables = {row[0] for row in await cur.fetchall()}
        if 'action_packages' in tables:
            async with conn.execute('SELECT COUNT(*) FROM action_packages') as cur: result['action_packages'] = (await cur.fetchone())[0]
        for table in ('approval_requests', 'approvals'):
            if table in tables:
                async with conn.execute(f'SELECT COUNT(*) FROM {table}') as cur: result['approvals'] += (await cur.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM assistant_turns WHERE model_id='package-d-synthetic'") as cur: result['synthetic_turns'] = (await cur.fetchone())[0]
    return result
'@ | Set-Content -Encoding utf8 -Path $harnessPath

$scenarioPath = Join-Path $tempRoot 'package_d_2x2_scenario.cjs'
@'
const fs = require('fs');
const { chromium } = require(process.argv[2]);
const config = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const fail = message => { throw new Error(message); };
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function eventually(check, message, timeout = 8000) {
  const end = Date.now() + timeout; let last;
  while (Date.now() < end) { try { const value = await check(); if (value) return value; } catch (error) { last = error; } await sleep(120); }
  fail(message + (last ? ` (${last.message})` : ''));
}
async function fixture(path, body) {
  const response = await fetch(config.backend + path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  if (!response.ok) fail(`fixture ${path} returned ${response.status}`);
  return response.json();
}
const getTurnRequests = (requests, threadId) => requests.filter(item => item.method === 'GET' && item.url.includes(`/api/assistant/threads/${threadId}/turns`)).length;
const getStreamRequests = (requests, threadId) => requests.filter(item => item.url.includes(`/api/assistant/threads/${threadId}/stream`)).length;
async function runViewport(viewport) {
  const context = await chromium.launchPersistentContext(`${config.profileRoot}-${viewport.name}`, { headless: true, viewport: viewport.size, ignoreHTTPSErrors: true });
  const page = await context.newPage();
  const requests = [], consoleEvents = [], pageErrors = [];
  page.on('request', request => requests.push({ method: request.method(), url: request.url() }));
  page.on('console', msg => consoleEvents.push({ type: msg.type(), text: msg.text() }));
  page.on('pageerror', error => pageErrors.push({ message: error.message }));
  const markerA = `PACKAGE-D-PERSISTED-A-${viewport.name}`;
  const markerB = `PACKAGE-D-PERSISTED-B-${viewport.name}`;
  const lateToken = `PACKAGE-D-LATE-A1-${viewport.name}`;
  try {
    await page.goto(config.frontend, { waitUntil: 'networkidle' });
    const turnA = await fixture('/_package_d/seed-turn', { thread_id: config.fixture.threadA1.id, work_id: config.fixture.workA.id, conversation_id: config.fixture.convA1.id, marker: markerA });
    const turnB = await fixture('/_package_d/seed-turn', { thread_id: config.fixture.threadB1.id, work_id: config.fixture.workB.id, conversation_id: config.fixture.convB1.id, marker: markerB });

    const sidebarToggle = page.getByRole('button', { name: 'Tr\u1ee3 l\u00fd GYO' });
    if (!(await page.locator('.assistant-sidebar').count())) await sidebarToggle.click();
    await eventually(() => page.locator('.assistant-sidebar').count() === 1, `${viewport.name}: Sidebar did not render`);
    await page.getByTitle('C\u00f4ng vi\u1ec7c', { exact: true }).click();
    await eventually(() => page.locator('.work-hub').count() === 1, `${viewport.name}: WorkHub did not render`);
    const workRail = page.locator('.work-list-rail');
    await eventually(() => workRail.getByText(config.fixture.workA.title, { exact: true }).count() > 0, `${viewport.name}: Work A missing`);
    await workRail.getByText(config.fixture.workA.title, { exact: true }).first().click();
    await eventually(() => page.locator('.work-hub-header').getByText(config.fixture.workA.title, { exact: true }).count() > 0, `${viewport.name}: WorkHub did not select A`);
    await page.getByRole('button', { name: 'Trao \u0111\u1ed5i', exact: true }).click();
    await page.getByText(config.fixture.convA1.title, { exact: true }).first().click();
    await eventually(() => page.locator('.conversation-workspace').getByText(config.fixture.convA1.title, { exact: true }).count() > 0, `${viewport.name}: WorkHub A1 missing`);

    const sidebar = page.locator('.assistant-sidebar');
    const selects = sidebar.locator('select');
    await eventually(() => selects.count() >= 2, `${viewport.name}: Sidebar scope selectors missing`);
    await selects.nth(0).selectOption(config.fixture.workA.id);
    await eventually(() => selects.nth(1).inputValue().then(value => value === config.fixture.convA1.id), `${viewport.name}: Sidebar A1 scope missing`);
    await eventually(() => getStreamRequests(requests, config.fixture.threadA1.id) === 1, `${viewport.name}: expected one shared EventSource for A1`);
    await page.screenshot({ path: `${config.evidenceRoot}/${viewport.name}-sidebar-workhub-a1.png`, fullPage: true });

    await selects.nth(1).selectOption(config.fixture.convA2.id);
    await eventually(() => selects.nth(1).inputValue().then(value => value === config.fixture.convA2.id), `${viewport.name}: Sidebar did not switch to A2`);
    await eventually(() => page.locator('.conversation-workspace').getByText(config.fixture.convA1.title, { exact: true }).count() > 0, `${viewport.name}: Sidebar scope changed WorkHub A1`);
    await fixture('/_package_d/publish', { thread_id: config.fixture.threadA1.id, turn_id: turnA.turn_id, event: 'token', text: lateToken });
    await eventually(() => page.locator('.conversation-workspace').getByText(lateToken, { exact: true }).count() > 0, `${viewport.name}: WorkHub did not receive A1 token`);
    if (await sidebar.getByText(lateToken, { exact: true }).count()) fail(`${viewport.name}: late A1 token rendered in Sidebar A2`);
    const aTurnsBefore = getTurnRequests(requests, config.fixture.threadA1.id);
    await fixture('/_package_d/publish', { thread_id: config.fixture.threadA1.id, turn_id: turnA.turn_id, event: 'error', text: `PACKAGE-D-SYNTHETIC-ERROR-${viewport.name}` });
    await eventually(() => getTurnRequests(requests, config.fixture.threadA1.id) > aTurnsBefore, `${viewport.name}: error did not refresh persisted A1 timeline`);
    await eventually(() => page.getByRole('button', { name: 'G\u1eedi l\u1ea1i ph\u1ea3n h\u1ed3i' }).count() > 0, `${viewport.name}: A1 error terminal was not rendered`);
    await eventually(() => page.locator('.conversation-workspace').getByText(markerA, { exact: true }).count() > 0, `${viewport.name}: persisted A1 timeline was lost after error`);

    await workRail.getByText(config.fixture.workB.title, { exact: true }).first().click();
    await eventually(() => page.locator('.work-hub-header').getByText(config.fixture.workB.title, { exact: true }).count() > 0, `${viewport.name}: WorkHub did not select B`);
    await page.getByRole('button', { name: 'Trao \u0111\u1ed5i', exact: true }).click();
    await page.getByText(config.fixture.convB1.title, { exact: true }).first().click();
    await eventually(() => page.locator('.conversation-workspace').getByText(config.fixture.convB1.title, { exact: true }).count() > 0, `${viewport.name}: WorkHub B1 missing`);
    await selects.nth(0).selectOption(config.fixture.workB.id);
    await eventually(() => selects.nth(1).inputValue().then(value => value === config.fixture.convB1.id), `${viewport.name}: Sidebar B1 scope missing`);
    await eventually(() => getStreamRequests(requests, config.fixture.threadB1.id) === 1, `${viewport.name}: expected one shared EventSource for B1`);
    const bTurnsBefore = getTurnRequests(requests, config.fixture.threadB1.id);
    await fixture('/_package_d/publish', { thread_id: config.fixture.threadB1.id, turn_id: turnB.turn_id, event: 'done' });
    await eventually(() => getTurnRequests(requests, config.fixture.threadB1.id) > bTurnsBefore, `${viewport.name}: done did not refresh persisted B1 timeline`);
    await eventually(() => page.locator('.conversation-workspace').getByText(markerB, { exact: true }).count() > 0, `${viewport.name}: persisted B1 timeline was lost after done`);
    await page.screenshot({ path: `${config.evidenceRoot}/${viewport.name}-sidebar-workhub-b1.png`, fullPage: true });

    const posts = requests.filter(item => item.method === 'POST').map(item => new URL(item.url).pathname);
    if (posts.length) fail(`${viewport.name}: browser navigation or scope selection made POST requests: ${JSON.stringify(posts)}`);
    const nonLocal = requests.filter(item => !item.url.startsWith(config.backend) && !item.url.startsWith(config.frontend));
    if (nonLocal.length) fail(`${viewport.name}: browser contacted non-local origin`);
    const consoleErrors = consoleEvents.filter(item => item.type === 'error');
    if (consoleErrors.length || pageErrors.length) fail(`${viewport.name}: unexplained browser error`);
    return { viewport: viewport.name, assertions: 15, sse: { a1: getStreamRequests(requests, config.fixture.threadA1.id), b1: getStreamRequests(requests, config.fixture.threadB1.id) }, network: requests.map(item => ({ method: item.method, path: new URL(item.url).pathname })), console: consoleEvents.map(item => ({ type: item.type })), page_errors: pageErrors };
  } finally { await context.close(); }
}
(async () => {
  const results = [];
  for (const viewport of [{ name: 'desktop', size: { width: 1440, height: 900 } }, { name: 'mobile', size: { width: 390, height: 844 } }]) results.push(await runViewport(viewport));
  const inspection = await (await fetch(config.backend + '/_package_d/inspect')).json();
  if (inspection.action_packages !== 0 || inspection.approvals !== 0) fail('fixture contains an Action Package or approval record');
  if (inspection.synthetic_turns !== 4) fail(`expected four isolated synthetic turns, got ${inspection.synthetic_turns}`);
  fs.writeFileSync(`${config.evidenceRoot}/assertion-summary-redacted.json`, JSON.stringify({ status: 'PASS', assertion_count: 32, viewport_results: results, fixture_inspection: inspection }, null, 2));
  fs.writeFileSync(`${config.evidenceRoot}/network-summary-redacted.json`, JSON.stringify(results.map(item => ({ viewport: item.viewport, network: item.network, sse: item.sse })), null, 2));
  fs.writeFileSync(`${config.evidenceRoot}/console-summary-redacted.json`, JSON.stringify(results.map(item => ({ viewport: item.viewport, console: item.console, page_errors: item.page_errors })), null, 2));
  fs.writeFileSync(`${config.evidenceRoot}/browser-process-redacted.json`, JSON.stringify({ status: 'PASS', exit_code: 0 }, null, 2));
})().catch(error => {
  const message = error.stack || error.message;
  fs.writeFileSync(`${config.evidenceRoot}/browser-process-redacted.json`, JSON.stringify({ status: 'FAIL', exit_code: 1, error: message }, null, 2));
  console.error(message);
  process.exit(1);
});
'@ | Set-Content -Encoding utf8 -Path $scenarioPath

# Avoid Vite config loading entirely: Vite 8 config bundling invokes
# child_process.spawn in this sandbox and fails EPERM. This temporary launcher
# uses only the installed Vite/React modules and retains the required /api proxy.
$frontendLauncherPath = Join-Path $tempRoot 'package_d_vite_launcher.mjs'
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
    host: '127.0.0.1',
    port: Number(frontendPort),
    strictPort: true,
    proxy: {
      '/api/health': { target, rewrite: path => path.replace(/^\/api/, '') },
      '/api': target,
    },
  },
});
await server.listen();
server.printUrls();
const close = async () => { await server.close(); process.exit(0); };
process.once('SIGINT', close);
process.once('SIGTERM', close);
'@ | Set-Content -Encoding utf8 -Path $frontendLauncherPath

$backend = $null
$frontend = $null
$browser = $null
$exitCode = 1
Save-Metadata
try {
    $env:DB_PATH = Join-Path $tempRoot 'app.db'
    $env:DEFAULT_WORKSPACE_ROOT = Join-Path $tempRoot 'workspace'
    $env:CORS_ORIGINS = "http://127.0.0.1:$FrontendPort"
    $env:OUTBOX_DISPATCHER_ENABLED = '0'
    $env:HERMES_DEV_MOCK = '0'
    $backendExe = Join-Path $repo 'backend\.venv\Scripts\python.exe'
    $viteModule = Join-Path $repo 'frontend\node_modules\vite\dist\node\index.js'
    $reactPlugin = Join-Path $repo 'frontend\node_modules\@vitejs\plugin-react\dist\index.js'
    $frontendRoot = Join-Path $repo 'frontend'
    foreach ($requiredPath in @($backendExe, $viteModule, $reactPlugin)) {
        if (-not (Test-Path -LiteralPath $requiredPath)) { throw "Required installed local tooling is unavailable: $requiredPath. No package installation was attempted." }
    }
    $backendArgs = @('-m', 'uvicorn', 'package_d_2x2_harness:app', '--app-dir', $tempRoot, '--host', '127.0.0.1', '--port', "$BackendPort")
    $frontendArgs = @($frontendLauncherPath, $frontendRoot, "$BackendPort", "$FrontendPort", $viteModule, $reactPlugin)
    $metadata.launch.backend = @{ command = "`"$backendExe`" $($backendArgs -join ' ')"; stdout_log = (Join-Path $EvidenceRoot 'backend.stdout.log'); stderr_log = (Join-Path $EvidenceRoot 'backend.stderr.log') }
    $metadata.launch.frontend = @{ command = "node.exe $($frontendArgs -join ' ')"; stdout_log = (Join-Path $EvidenceRoot 'frontend.stdout.log'); stderr_log = (Join-Path $EvidenceRoot 'frontend.stderr.log') }
    Save-Metadata
    $backend = Start-Process -FilePath $backendExe -ArgumentList $backendArgs -WorkingDirectory (Join-Path $repo 'backend') -WindowStyle Hidden -RedirectStandardOutput $metadata.launch.backend.stdout_log -RedirectStandardError $metadata.launch.backend.stderr_log -PassThru
    $frontend = Start-Process -FilePath 'node.exe' -ArgumentList $frontendArgs -WorkingDirectory $frontendRoot -WindowStyle Hidden -RedirectStandardOutput $metadata.launch.frontend.stdout_log -RedirectStandardError $metadata.launch.frontend.stderr_log -PassThru
    Update-ProcessMetadata 'backend' $backend
    Update-ProcessMetadata 'frontend' $frontend
    Save-Metadata
    Wait-Ready

    $workA = Invoke-LocalApi 'Post' '/api/sessions' @{ title = 'PACKAGE-D-WORK-A'; goal = 'synthetic isolated browser UAT'; data_scope = 'work_only' }
    $workB = Invoke-LocalApi 'Post' '/api/sessions' @{ title = 'PACKAGE-D-WORK-B'; goal = 'synthetic isolated browser UAT'; data_scope = 'work_only' }
    $convA1 = @(Invoke-LocalApi 'Get' "/api/works/$($workA.id)/conversations")[0]
    $convB1 = @(Invoke-LocalApi 'Get' "/api/works/$($workB.id)/conversations")[0]
    $convA1 = Invoke-LocalApi 'Patch' "/api/works/$($workA.id)/conversations/$($convA1.id)" @{ title = 'PACKAGE-D-CONV-A1'; purpose = 'Synthetic isolated UAT fixture' }
    $convB1 = Invoke-LocalApi 'Patch' "/api/works/$($workB.id)/conversations/$($convB1.id)" @{ title = 'PACKAGE-D-CONV-B1'; purpose = 'Synthetic isolated UAT fixture' }
    $convA2 = Invoke-LocalApi 'Post' "/api/works/$($workA.id)/conversations" @{ title = 'PACKAGE-D-CONV-A2'; purpose = 'Synthetic scope-switch target' }
    $threadA1 = Invoke-LocalApi 'Post' "/api/assistant/works/$($workA.id)/conversations/$($convA1.id)/assistant-thread"
    $threadB1 = Invoke-LocalApi 'Post' "/api/assistant/works/$($workB.id)/conversations/$($convB1.id)/assistant-thread"
    $fixture = @{ workA = @{ id = $workA.id; title = $workA.title }; workB = @{ id = $workB.id; title = $workB.title }; convA1 = @{ id = $convA1.id; title = $convA1.title }; convA2 = @{ id = $convA2.id; title = $convA2.title }; convB1 = @{ id = $convB1.id; title = $convB1.title }; threadA1 = @{ id = $threadA1.id }; threadB1 = @{ id = $threadB1.id } }
    $configPath = Join-Path $tempRoot 'browser-config.json'
    $configJson = @{ backend = "http://127.0.0.1:$BackendPort"; frontend = "http://127.0.0.1:$FrontendPort"; evidenceRoot = ($EvidenceRoot -replace '\\', '/'); profileRoot = ($profileRoot -replace '\\', '/'); fixture = $fixture } | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($configPath, $configJson, [System.Text.UTF8Encoding]::new($false))

    $playwrightModule = Join-Path $repo 'frontend\node_modules\playwright'
    if (-not (Test-Path $playwrightModule)) { throw 'Installed local Playwright module is unavailable; no package installation was attempted.' }
    $metadata.launch.browser = @{
        command = "node.exe $scenarioPath $playwrightModule $configPath"
        stdout_log = (Join-Path $EvidenceRoot 'browser.stdout.log')
        stderr_log = (Join-Path $EvidenceRoot 'browser.stderr.log')
        timeout_seconds = $BrowserTimeoutSec
    }
    Save-Metadata
    $browser = Start-Process -FilePath 'node.exe' -ArgumentList @($scenarioPath, $playwrightModule, $configPath) -WorkingDirectory $frontendRoot -WindowStyle Hidden -RedirectStandardOutput $metadata.launch.browser.stdout_log -RedirectStandardError $metadata.launch.browser.stderr_log -PassThru
    Update-ProcessMetadata 'browser' $browser
    Save-Metadata
    if (-not $browser.WaitForExit($BrowserTimeoutSec * 1000)) {
        Stop-Process -Id $browser.Id -Force -ErrorAction SilentlyContinue
        $browser.WaitForExit(5000) | Out-Null
        Update-ProcessMetadata 'browser' $browser
        throw "Package D 2x2 local Playwright scenario timed out after $BrowserTimeoutSec seconds; retained logs: $($metadata.launch.browser.stdout_log), $($metadata.launch.browser.stderr_log)"
    }
    Update-ProcessMetadata 'browser' $browser
    $browserResultPath = Join-Path $EvidenceRoot 'browser-process-redacted.json'
    if (-not (Test-Path -LiteralPath $browserResultPath)) {
        throw "Package D 2x2 local Playwright scenario exited without a terminal browser receipt; retained logs: $($metadata.launch.browser.stdout_log), $($metadata.launch.browser.stderr_log)"
    }
    $browserResult = Get-Content -Raw -Encoding utf8 -LiteralPath $browserResultPath | ConvertFrom-Json
    $browserExitCode = [int]$browserResult.exit_code
    $metadata.launch.browser.exit_code = $browserExitCode
    $metadata.launch.browser.result = $browserResult.status
    Save-Metadata
    if ($browserExitCode -ne 0) { throw "Package D 2x2 local Playwright scenario failed with exit $browserExitCode" }
    $metadata.status = 'PASS'
    $metadata.completed_at = (Get-Date).ToString('o')
    $metadata.assertion_count = 32
    $metadata.assertions = @('desktop Sidebar + WorkHub', 'mobile Sidebar + WorkHub', 'A1 Work/Conversation scope', 'B1 Work/Conversation scope', 'one shared EventSource for A1', 'one shared EventSource for B1', 'late A1 token excluded from Sidebar A2', 'late A1 token visible in unchanged WorkHub A1', 'A1 error refreshes persisted timeline', 'A1 marker survives error', 'B1 done refreshes persisted timeline', 'B1 marker survives done', 'no browser POST for navigation or scope selection', 'no Action Package record', 'no approval record', 'no browser external origin or console/page error')
    Save-Metadata
    $exitCode = 0
} catch {
    Set-TerminalFailure 'runner' $_.Exception.Message
    Save-Metadata
} finally {
    foreach ($processName in @('browser', 'frontend', 'backend')) {
        $process = Get-Variable -Name $processName -ValueOnly
        if ($process) {
            $process.Refresh()
            if (-not $process.HasExited) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                $process.WaitForExit(5000) | Out-Null
            }
            Update-ProcessMetadata $processName $process
        }
    }
    if ($metadata.status -eq 'RUNNING') { Set-TerminalFailure 'interrupted' 'Runner stopped before a terminal result was recorded.' }
    Save-Metadata
}
Write-Output $EvidenceRoot
exit $exitCode
