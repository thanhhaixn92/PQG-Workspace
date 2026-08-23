[CmdletBinding()]
param(
    [string]$EvidenceRoot,
    [int]$BackendPort = 0,
    [int]$FrontendPort = 0
)

# Compatibility entrypoint only. The sole canonical Package D runner is the
# 2x2 runner below; forwarding prevents the legacy narrower scenario from
# becoming a second source of browser evidence.
& (Join-Path $PSScriptRoot 'run-package-d-browser-uat-2x2.ps1') @PSBoundParameters
exit $LASTEXITCODE

<# Historical implementation retained only to avoid a destructive edit in an
   already-dirty worktree. It is unreachable and cannot execute.

# Package D only. This runner starts product FastAPI against a disposable DB
# and adds a process-local synthetic SSE fixture endpoint. The browser never
# talks to that endpoint; it continues to use product REST/SSE routes.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if (-not $EvidenceRoot) { $EvidenceRoot = Join-Path $repo "output\playwright\package-d-$stamp" }
$EvidenceRoot = [System.IO.Path]::GetFullPath($EvidenceRoot)
$tempRoot = Join-Path $env:TEMP "pqg-package-d-$stamp"
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
    status = 'RUNNING'
    started_at = (Get-Date).ToString('o')
    completed_at = $null
    isolation = @{ database = 'temporary'; workspace = 'temporary'; browser_profile = 'temporary'; provider = 'not configured or called'; external_network = 'not used'; credentials = 'not read or written' }
    ports = @{ backend = $BackendPort; frontend = $FrontendPort }
    assertions = @()
}
function Save-Metadata { $metadata | ConvertTo-Json -Depth 12 | Set-Content -Encoding utf8 -Path (Join-Path $EvidenceRoot 'run-metadata.json') }
function Invoke-LocalApi([string]$Method, [string]$Path, $Body = $null) {
    $params = @{ Uri = "http://127.0.0.1:$BackendPort$Path"; Method = $Method; ContentType = 'application/json'; TimeoutSec = 15 }
    if ($null -ne $Body) { $params.Body = $Body | ConvertTo-Json -Depth 10 -Compress }
    Invoke-RestMethod @params
}
function Wait-Ready {
    for ($n = 0; $n -lt 100; $n++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSec 2
            $page = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -UseBasicParsing -TimeoutSec 2
            if ($health.status -eq 'ok' -and $page.StatusCode -eq 200) { return }
        } catch { Start-Sleep -Milliseconds 250 }
    }
    throw 'Temporary Package D services did not become ready.'
}

# This harness lives outside the repository and is process-local to the
# disposable FastAPI runtime. It creates synthetic persisted turns and emits
# redaction-safe token/error/done events through the product event bus.
$harnessPath = Join-Path $tempRoot 'package_d_harness.py'
@'
import json
import os
import time
import uuid
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

def _db():
    return os.environ['DB_PATH']

@app.post('/_package_d/seed-turn')
async def seed_turn(request: SeedTurn):
    turn_id = 'package-d-turn-' + uuid.uuid4().hex
    now = int(time.time())
    async with aiosqlite.connect(_db()) as conn:
        await conn.execute("INSERT INTO assistant_turns (id, thread_id, work_id, conversation_id, role, status, model_id, created_at) VALUES (?, ?, ?, ?, 'assistant', 'running', 'package-d-synthetic', ?)", (turn_id, request.thread_id, request.work_id, request.conversation_id, now))
        await conn.execute("INSERT INTO assistant_turn_parts (id, turn_id, part_type, content_json, sort_order, created_at) VALUES (?, ?, 'text', ?, 0, ?)", (uuid.uuid4().hex, turn_id, json.dumps({'text': request.marker}), now))
        await conn.commit()
    return {'turn_id': turn_id}

@app.post('/_package_d/publish')
async def publish(request: Publish):
    channel = 'assistant:' + request.thread_id
    if request.event == 'token':
        await event_bus.publish(channel, SseTokenEvent(text=request.text, assistant_turn_id=request.turn_id, thread_id=request.thread_id))
        return {'published': 'token'}
    if request.event not in {'done', 'error'}:
        raise HTTPException(status_code=400, detail='Unsupported synthetic event')
    now = int(time.time())
    status = 'completed' if request.event == 'done' else 'failed'
    message = request.text or 'PACKAGE-D-SYNTHETIC-TERMINAL'
    async with aiosqlite.connect(_db()) as conn:
        changed = await conn.execute("UPDATE assistant_turns SET status = ?, completed_at = ?, error = ? WHERE id = ? AND status = 'running'", (status, now, message if status == 'failed' else None, request.turn_id))
        if changed.rowcount != 1:
            raise HTTPException(status_code=409, detail='Synthetic turn is not running')
        await conn.commit()
    if request.event == 'done':
        await event_bus.publish(channel, SseDoneEvent(assistant_turn_id=request.turn_id, thread_id=request.thread_id))
    else:
        await event_bus.publish(channel, SseErrorEvent(message=message, assistant_turn_id=request.turn_id, thread_id=request.thread_id))
    return {'published': request.event}

@app.get('/_package_d/inspect')
async def inspect_fixture():
    result = {'action_packages': 0, 'approvals': 0, 'synthetic_turns': 0}
    async with aiosqlite.connect(_db()) as conn:
        async with conn.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
            tables = {row[0] for row in await cur.fetchall()}
        if 'action_packages' in tables:
            async with conn.execute('SELECT COUNT(*) FROM action_packages') as cur: result['action_packages'] = (await cur.fetchone())[0]
        for table in ('approval_requests', 'approvals'):
            if table in tables:
                async with conn.execute(f'SELECT COUNT(*) FROM {table}') as cur: result['approvals'] += (await cur.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM assistant_turns WHERE model_id='package-d-synthetic'") as cur:
            result['synthetic_turns'] = (await cur.fetchone())[0]
    return result
'@ | Set-Content -Encoding utf8 -Path $harnessPath

$browserScenarioPath = Join-Path $tempRoot 'package_d_browser_scenario.cjs'
@'
const fs = require('fs');
const { chromium } = require(process.argv[2]);
const config = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const evidence = config.evidenceRoot;

const fail = (message) => { throw new Error(message); };
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
async function eventually(check, message, timeout = 8000) {
  const deadline = Date.now() + timeout;
  let last;
  while (Date.now() < deadline) {
    try { const value = await check(); if (value) return value; } catch (error) { last = error; }
    await sleep(120);
  }
  fail(message + (last ? ` (${last.message})` : ''));
}
async function api(path, body) {
  const result = await fetch(config.backend + path, { method: 'POST', headers: {'content-type':'application/json'}, body: JSON.stringify(body) });
  if (!result.ok) fail(`fixture endpoint ${path} returned ${result.status}`);
  return result.json();
}
async function runViewport(viewport) {
  const browser = await chromium.launchPersistentContext(config.profileRoot + '-' + viewport.name, { headless: true, viewport: viewport.size, ignoreHTTPSErrors: true });
  const page = await browser.newPage();
  const requests = [], consoleEvents = [], pageErrors = [];
  page.on('request', request => requests.push({ method: request.method(), url: request.url() }));
  page.on('console', msg => consoleEvents.push({ type: msg.type(), text: msg.text() }));
  page.on('pageerror', error => pageErrors.push({ message: error.message }));
  try {
    await page.goto(config.frontend, { waitUntil: 'networkidle' });
    const assistantToggle = page.getByRole('button', { name: 'Trợ lý GYO' });
    if (!(await page.locator('.assistant-sidebar').count())) await assistantToggle.click();
    await eventually(() => page.locator('.assistant-sidebar').count() === 1, `${viewport.name}: Sidebar did not render`);
    await page.getByTitle('Công việc', { exact: true }).click();
    await eventually(() => page.locator('.work-hub').count() === 1, `${viewport.name}: WorkHub did not render`);
    const workRail = page.locator('.work-list-rail');
    await eventually(() => workRail.getByText(config.fixture.workA.title, { exact: true }).count() > 0, `${viewport.name}: Work A missing from WorkHub rail`);
    await workRail.getByText(config.fixture.workA.title, { exact: true }).first().click();
    await eventually(() => page.locator('.work-hub-header').getByText(config.fixture.workA.title, { exact: true }).count() > 0, `${viewport.name}: WorkHub did not select Work A`);
    await page.getByRole('button', { name: 'Trao đổi', exact: true }).click();
    await eventually(() => page.getByText(config.fixture.convA1.title, { exact: true }).count() > 0, `${viewport.name}: Work Conversation A1 missing`);
    await page.getByText(config.fixture.convA1.title, { exact: true }).first().click();
    await eventually(() => page.locator('.conversation-workspace').getByText(config.fixture.convA1.title, { exact: true }).count() > 0, `${viewport.name}: WorkHub Conversation A1 did not render`);

    const sidebar = page.locator('.assistant-sidebar');
    const selects = sidebar.locator('select');
    await eventually(() => selects.count() >= 2, `${viewport.name}: Sidebar scope selectors missing`);
    await selects.nth(0).selectOption(config.fixture.workA.id);
    await eventually(() => selects.nth(1).inputValue().then(value => value === config.fixture.convA1.id), `${viewport.name}: Sidebar did not select Conversation A1`);
    await eventually(() => requests.filter(item => item.url.includes('/api/assistant/threads/' + config.fixture.threadA1.id + '/stream')).length === 1, `${viewport.name}: expected exactly one shared EventSource for A1`);
    await page.screenshot({ path: `${evidence}/${viewport.name}-sidebar-workhub-a1.png`, fullPage: true });

    await selects.nth(1).selectOption(config.fixture.convA2.id);
    await eventually(() => selects.nth(1).inputValue().then(value => value === config.fixture.convA2.id), `${viewport.name}: Sidebar did not change scope to A2`);
    await eventually(() => page.locator('.conversation-workspace').getByText(config.fixture.convA1.title, { exact: true }).count() > 0, `${viewport.name}: WorkHub A1 unexpectedly changed while Sidebar scope changed`);
    await api('/_package_d/publish', { thread_id: config.fixture.threadA1.id, turn_id: config.fixture.turnA1, event: 'token', text: config.fixture.lateToken });
    await eventually(() => page.locator('.conversation-workspace').getByText(config.fixture.lateToken, { exact: true }).count() > 0, `${viewport.name}: WorkHub did not receive synthetic A1 SSE token`);
    if (await sidebar.getByText(config.fixture.lateToken, { exact: true }).count()) fail(`${viewport.name}: late A1 SSE token rendered in Sidebar A2 scope`);
    await api('/_package_d/publish', { thread_id: config.fixture.threadA1.id, turn_id: config.fixture.turnA1, event: 'error', text: 'PACKAGE-D-SYNTHETIC-ERROR' });
    await eventually(() => page.locator('.conversation-workspace').getByText(config.fixture.markerA, { exact: true }).count() > 0, `${viewport.name}: persisted A1 timeline was cleared by error terminal`);

    await workRail.getByText(config.fixture.workB.title, { exact: true }).first().click();
    await eventually(() => page.locator('.work-hub-header').getByText(config.fixture.workB.title, { exact: true }).count() > 0, `${viewport.name}: WorkHub did not select Work B`);
    await page.getByRole('button', { name: 'Trao đổi', exact: true }).click();
    await page.getByText(config.fixture.convB1.title, { exact: true }).first().click();
    await eventually(() => page.locator('.conversation-workspace').getByText(config.fixture.convB1.title, { exact: true }).count() > 0, `${viewport.name}: WorkHub Conversation B1 did not render`);
    await selects.nth(0).selectOption(config.fixture.workB.id);
    await eventually(() => selects.nth(1).inputValue().then(value => value === config.fixture.convB1.id), `${viewport.name}: Sidebar did not select Work B Conversation B1`);
    await eventually(() => requests.filter(item => item.url.includes('/api/assistant/threads/' + config.fixture.threadB1.id + '/stream')).length === 1, `${viewport.name}: expected exactly one shared EventSource for B1`);
    await api('/_package_d/publish', { thread_id: config.fixture.threadB1.id, turn_id: config.fixture.turnB1, event: 'done' });
    await eventually(() => page.locator('.conversation-workspace').getByText(config.fixture.markerB, { exact: true }).count() > 0, `${viewport.name}: persisted B1 timeline was cleared by done terminal`);
    await page.screenshot({ path: `${evidence}/${viewport.name}-sidebar-workhub-b1.png`, fullPage: true });

    const pagePosts = requests.filter(item => item.method === 'POST').map(item => new URL(item.url).pathname);
    if (pagePosts.length) fail(`${viewport.name}: navigation/scope switch made POST requests: ${JSON.stringify(pagePosts)}`);
    const external = requests.filter(item => !item.url.startsWith(config.backend) && !item.url.startsWith(config.frontend));
    if (external.length) fail(`${viewport.name}: browser contacted a non-local origin`);
    const consoleErrors = consoleEvents.filter(item => item.type === 'error');
    if (consoleErrors.length || pageErrors.length) fail(`${viewport.name}: unexplained browser errors`);
    return { viewport: viewport.name, assertions: 10, network: requests.map(item => ({ method: item.method, path: new URL(item.url).pathname })), console: consoleEvents.map(item => ({ type: item.type })), page_errors: pageErrors, sse: { a1: 1, b1: 1 } };
  } finally { await browser.close(); }
}
(async () => {
  const results = [];
  for (const viewport of [{name:'desktop',size:{width:1440,height:900}},{name:'mobile',size:{width:390,height:844}}]) results.push(await runViewport(viewport));
  const inspect = await (await fetch(config.backend + '/_package_d/inspect')).json();
  if (inspect.action_packages !== 0 || inspect.approvals !== 0) fail('Synthetic fixture contains an Action Package or approval record');
  fs.writeFileSync(`${evidence}/assertion-summary-redacted.json`, JSON.stringify({status:'PASS', viewport_results:results, fixture_inspection:inspect}, null, 2));
  fs.writeFileSync(`${evidence}/network-summary-redacted.json`, JSON.stringify(results.map(item => ({viewport:item.viewport,network:item.network,sse:item.sse})), null, 2));
  fs.writeFileSync(`${evidence}/console-summary-redacted.json`, JSON.stringify(results.map(item => ({viewport:item.viewport,console:item.console,page_errors:item.page_errors})), null, 2));
})().catch(error => { console.error(error.stack || error.message); process.exit(1); });
'@ | Set-Content -Encoding utf8 -Path $browserScenarioPath

$backend = $null
$frontend = $null
Save-Metadata
try {
    $env:DB_PATH = Join-Path $tempRoot 'app.db'
    $env:DEFAULT_WORKSPACE_ROOT = Join-Path $tempRoot 'workspace'
    $env:CORS_ORIGINS = "http://127.0.0.1:$FrontendPort"
    $env:OUTBOX_DISPATCHER_ENABLED = '0'
    $env:HERMES_DEV_MOCK = '0'
    $env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
    Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue

    $backend = Start-Process -FilePath (Join-Path $repo 'backend\.venv\Scripts\python.exe') -ArgumentList @('-m','uvicorn','package_d_harness:app','--app-dir',$tempRoot,'--host','127.0.0.1','--port',"$BackendPort") -WorkingDirectory (Join-Path $repo 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $EvidenceRoot 'backend.stdout.log') -RedirectStandardError (Join-Path $EvidenceRoot 'backend.stderr.log') -PassThru
    $frontend = Start-Process -FilePath 'node.exe' -ArgumentList @((Join-Path $repo 'frontend\node_modules\vite\bin\vite.js'),'--host','127.0.0.1','--port',"$FrontendPort",'--strictPort') -WorkingDirectory (Join-Path $repo 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $EvidenceRoot 'frontend.stdout.log') -RedirectStandardError (Join-Path $EvidenceRoot 'frontend.stderr.log') -PassThru
    Wait-Ready

    $workA = Invoke-LocalApi 'Post' '/api/sessions' @{ title='PACKAGE-D-WORK-A'; goal='synthetic browser UAT'; data_scope='work_only' }
    $workB = Invoke-LocalApi 'Post' '/api/sessions' @{ title='PACKAGE-D-WORK-B'; goal='synthetic browser UAT'; data_scope='work_only' }
    $convA1 = @(Invoke-LocalApi 'Get' "/api/works/$($workA.id)/conversations")[0]
    $convB1 = @(Invoke-LocalApi 'Get' "/api/works/$($workB.id)/conversations")[0]
    $convA1 = Invoke-LocalApi 'Patch' "/api/works/$($workA.id)/conversations/$($convA1.id)" @{ title='PACKAGE-D-CONV-A1'; purpose='Synthetic isolated UAT fixture' }
    $convB1 = Invoke-LocalApi 'Patch' "/api/works/$($workB.id)/conversations/$($convB1.id)" @{ title='PACKAGE-D-CONV-B1'; purpose='Synthetic isolated UAT fixture' }
    $convA2 = Invoke-LocalApi 'Post' "/api/works/$($workA.id)/conversations" @{ title='PACKAGE-D-CONV-A2'; purpose='Synthetic scope-switch target' }
    $threadA1 = Invoke-LocalApi 'Post' "/api/assistant/works/$($workA.id)/conversations/$($convA1.id)/assistant-thread"
    $threadB1 = Invoke-LocalApi 'Post' "/api/assistant/works/$($workB.id)/conversations/$($convB1.id)/assistant-thread"
    $turnA1 = Invoke-LocalApi 'Post' '/_package_d/seed-turn' @{ thread_id=$threadA1.id; work_id=$workA.id; conversation_id=$convA1.id; marker='PACKAGE-D-PERSISTED-A' }
    $turnB1 = Invoke-LocalApi 'Post' '/_package_d/seed-turn' @{ thread_id=$threadB1.id; work_id=$workB.id; conversation_id=$convB1.id; marker='PACKAGE-D-PERSISTED-B' }
    $fixture = @{ workA=@{id=$workA.id; title=$workA.title}; workB=@{id=$workB.id; title=$workB.title}; convA1=@{id=$convA1.id; title=$convA1.title}; convA2=@{id=$convA2.id; title=$convA2.title}; convB1=@{id=$convB1.id; title=$convB1.title}; threadA1=@{id=$threadA1.id}; threadB1=@{id=$threadB1.id}; turnA1=$turnA1.turn_id; turnB1=$turnB1.turn_id; markerA='PACKAGE-D-PERSISTED-A'; markerB='PACKAGE-D-PERSISTED-B'; lateToken='PACKAGE-D-LATE-A1' }
    $configPath = Join-Path $tempRoot 'browser-config.json'
    @{ backend="http://127.0.0.1:$BackendPort"; frontend="http://127.0.0.1:$FrontendPort"; evidenceRoot=($EvidenceRoot -replace '\\','/'); profileRoot=($profileRoot -replace '\\','/'); fixture=$fixture } | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 -Path $configPath

    $playwrightModule = Join-Path $repo 'frontend\node_modules\playwright'
    & node.exe $browserScenarioPath $playwrightModule $configPath 2>&1 | Tee-Object -FilePath (Join-Path $EvidenceRoot 'browser-run.log')
    if ($LASTEXITCODE -ne 0) { throw "Package D local Playwright scenario failed with exit $LASTEXITCODE" }
    $metadata.status = 'PASS'
    $metadata.completed_at = (Get-Date).ToString('o')
    $metadata.assertions = @('desktop Sidebar + WorkHub', 'mobile Sidebar + WorkHub', 'Work and Conversation scopes are distinct', 'one EventSource per active thread across both surfaces', 'late A1 token is absent from Sidebar A2 after scope switch', 'persisted timeline survives SSE error', 'persisted timeline survives SSE done', 'no browser POST navigation/scope mutation', 'no Action Package or approval record', 'no external provider/network or browser error')
    Save-Metadata
    Write-Output $EvidenceRoot
} catch {
    $metadata.status = 'FAIL'
    $metadata.completed_at = (Get-Date).ToString('o')
    $metadata.error = $_.Exception.Message
    Save-Metadata
    throw
} finally {
    if ($frontend -and -not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force }
    if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force }
}
#>
