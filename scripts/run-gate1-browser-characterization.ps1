param(
    [Parameter(Mandatory = $true)]
    [string]$EvidenceRoot,
    [int]$BackendPort = 0,
    [int]$FrontendPort = 0
)

# Gate 1-only disposable browser harness. No provider is called: the backend
# starts in HERMES_DEV_MOCK mode and the browser performs navigation only.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$EvidenceRoot = [System.IO.Path]::GetFullPath($EvidenceRoot)
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$tempRoot = Join-Path $env:TEMP "gate1-browser-$stamp"
New-Item -ItemType Directory -Force -Path $EvidenceRoot, $tempRoot, (Join-Path $tempRoot 'workspace') | Out-Null

function Get-FreePort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    try { $listener.Start(); return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}
if ($BackendPort -eq 0) { $BackendPort = Get-FreePort }
if ($FrontendPort -eq 0) { $FrontendPort = Get-FreePort }
if ($BackendPort -eq $FrontendPort) { throw 'Ports must differ.' }

$session = "gate1-$stamp"
$cli = @('--yes', '--package', '@playwright/cli', 'playwright-cli', "-s=$session")
$backend = $null
$frontend = $null
$metadata = [ordered]@{
    schema_version = 1
    status = 'RUNNING'
    started_at = (Get-Date).ToString('o')
    completed_at = $null
    temp_data = @{ sqlite = 'temporary'; workspace = 'temporary'; browser_profile = "playwright-cli-session:$session" }
    provider = 'not_called; HERMES_DEV_MOCK=1'
    ports = @{ backend = $BackendPort; frontend = $FrontendPort }
    checks = @()
}
function Save-Metadata { $metadata | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 -Path (Join-Path $EvidenceRoot 'run-metadata.json') }
function Invoke-Cli([string[]]$Arguments, [string]$Log) {
    # npx emits informational notices on stderr.  Keep them in the raw CLI log
    # without letting PowerShell's Stop preference misclassify them as a runner failure.
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $out = & npx @cli @Arguments 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    $out | Set-Content -Encoding utf8 -Path (Join-Path $EvidenceRoot $Log)
    if ($code -ne 0) { throw "playwright-cli failed with exit $code for $($Arguments[0])" }
    return $out
}
function Wait-Ready {
    for ($n = 0; $n -lt 80; $n++) {
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:$BackendPort/health" -TimeoutSec 2
            $page = Invoke-WebRequest "http://127.0.0.1:$FrontendPort" -UseBasicParsing -TimeoutSec 2
            if ($health.status -eq 'ok' -and $page.StatusCode -eq 200) { return }
        } catch { Start-Sleep -Milliseconds 250 }
    }
    throw 'Temporary services did not become ready.'
}
function Invoke-Api([string]$Method, [string]$Path, $Body = $null) {
    $args = @{ Uri = "http://127.0.0.1:$BackendPort$Path"; Method = $Method; ContentType = 'application/json' }
    if ($null -ne $Body) { $args.Body = ($Body | ConvertTo-Json -Depth 8) }
    return Invoke-RestMethod @args
}

function Seed-VisibleTimelineFixture(
    [string]$WorkA,
    [string]$ConversationA,
    [string]$WorkB,
    [string]$ConversationB
) {
    # This writes only to the disposable DB after the app schema exists. It
    # creates no prompt, provider call, task run, or assistant turn.
    $seedPath = Join-Path $tempRoot 'seed_gate1_timeline.py'
    @'
import sqlite3
import sys
import time
import uuid

db_path, work_a, conversation_a, work_b, conversation_b = sys.argv[1:]
now = int(time.time())
rows = [
    (str(uuid.uuid4()), work_a, None, 'assistant', 'G1-WC-MARKER-A', now, conversation_a),
    (str(uuid.uuid4()), work_b, None, 'assistant', 'G1-WC-MARKER-B', now, conversation_b),
]
with sqlite3.connect(db_path) as conn:
    conn.executemany(
        'INSERT INTO chat_messages (id, session_id, task_id, role, content, created_at, conversation_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
        rows,
    )
    conn.commit()
'@ | Set-Content -Encoding utf8 -Path $seedPath
    $null = & (Join-Path $repo 'backend\.venv\Scripts\python.exe') $seedPath $env:DB_PATH $WorkA $ConversationA $WorkB $ConversationB 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Temporary visible-timeline fixture seed failed.' }
}

Save-Metadata
try {
    $env:DB_PATH = Join-Path $tempRoot 'app.db'
    $env:DEFAULT_WORKSPACE_ROOT = Join-Path $tempRoot 'workspace'
    $env:CORS_ORIGINS = "http://127.0.0.1:$FrontendPort"
    $env:HERMES_DEV_MOCK = '1'
    $env:OUTBOX_DISPATCHER_ENABLED = '0'
    $env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
    $env:VITE_SHOW_TEST_WORKS = '1'
    Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue

    $backend = Start-Process -FilePath (Join-Path $repo 'backend\.venv\Scripts\python.exe') -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$BackendPort") -WorkingDirectory (Join-Path $repo 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $EvidenceRoot 'backend.stdout.log') -RedirectStandardError (Join-Path $EvidenceRoot 'backend.stderr.log') -PassThru
    $frontend = Start-Process -FilePath 'node.exe' -ArgumentList @((Join-Path $repo 'frontend\node_modules\vite\bin\vite.js'),'--host','127.0.0.1','--port',"$FrontendPort",'--strictPort') -WorkingDirectory (Join-Path $repo 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $EvidenceRoot 'frontend.stdout.log') -RedirectStandardError (Join-Path $EvidenceRoot 'frontend.stderr.log') -PassThru
    Wait-Ready

    # Safe fixtures: two Works, one visible Work Conversation and one unbound
    # GYO thread each. Labels are synthetic and contain no user content.
    $workA = Invoke-Api 'Post' '/api/sessions' @{ title='gate1-work-a'; goal='gate1'; data_scope='work_only' }
    $workB = Invoke-Api 'Post' '/api/sessions' @{ title='gate1-work-b'; goal='gate1'; data_scope='work_only' }
    # Session creation seeds one empty Work Conversation. Do not add a second
    # conversation; the scenario must remain minimal and prompt-free.
    $conversationsA = @([object[]](Invoke-Api 'Get' "/api/works/$($workA.id)/conversations"))
    $conversationsB = @([object[]](Invoke-Api 'Get' "/api/works/$($workB.id)/conversations"))
    $conversationA = $conversationsA[0]
    $conversationB = $conversationsB[0]
    $conversationA = Invoke-Api 'Patch' "/api/works/$($workA.id)/conversations/$($conversationA.id)" @{ title='G1-WC-A'; purpose='Gate 1 fixture' }
    $conversationB = Invoke-Api 'Patch' "/api/works/$($workB.id)/conversations/$($conversationB.id)" @{ title='G1-WC-B'; purpose='Gate 1 fixture' }
    Seed-VisibleTimelineFixture $workA.id $conversationA.id $workB.id $conversationB.id
    $threadA = Invoke-Api 'Post' '/api/assistant/threads' @{ title='G1-GYO-A'; work_id=$workA.id }
    $threadB = Invoke-Api 'Post' '/api/assistant/threads' @{ title='G1-GYO-B'; work_id=$workB.id }
    if ($threadA.conversation_id -or $threadB.conversation_id) { throw 'Seeded GYO threads unexpectedly bound to a Work Conversation.' }
    if ($conversationA.id -eq $conversationB.id -or $threadA.id -eq $threadB.id) { throw 'Seed identifiers are not isolated.' }
    $allThreads = @([object[]](Invoke-Api 'Get' '/api/assistant/threads?include_archived=true'))
    $threadsA = @($allThreads | Where-Object { $_.work_id -eq $workA.id })
    $threadsB = @($allThreads | Where-Object { $_.work_id -eq $workB.id })
    $metadata.seed_debug = @{ all_threads = $allThreads.Count; threads_a = $threadsA.Count; threads_b = $threadsB.Count; conversations_a = $conversationsA.Count; conversations_b = $conversationsB.Count }
    if ($threadsA.Count -ne 1 -or $threadsB.Count -ne 1 -or $threadsA[0].conversation_id -or $threadsB[0].conversation_id) { throw 'GYO history seed crossed Work or Work Conversation boundaries.' }
    if ($conversationsA.Count -ne 1 -or $conversationsB.Count -ne 1 -or $conversationsA[0].id -eq $conversationsB[0].id) { throw 'Work Conversation seed crossed Work boundaries.' }
    $metadata.seed_isolation = @{ work_conversations_per_work = 1; gyo_threads_per_work = 1; gyo_threads_bound_to_conversation = 0; cross_work_records = 0 }

    Invoke-Cli @('open', "http://127.0.0.1:$FrontendPort") 'playwright-open.log' | Out-Null
    $rootJson = ConvertTo-Json (($EvidenceRoot -replace '\\','/')) -Compress
    $code = @"
async (page) => {
  const root = $rootJson;
  const stamp = () => new Date().toISOString();
  const requests = [], consoleEvents = [], pageErrors = [];
  const normalize = value => String(value)
    .replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, ':id')
    .replace(/[?].*$/, '');
  const created = url => /\/api\/works\/[^/]+\/conversations$|\/api\/assistant\/threads$|\/api\/assistant\/threads\/[^/]+\/runs$|\/turns$/.test(url);
  page.on('request', req => { if (req.method() === 'POST') requests.push({method:req.method(), endpoint:normalize(new URL(req.url()).pathname), at:stamp(), creates:created(new URL(req.url()).pathname)}); });
  page.on('response', res => { const item = requests.findLast(x => x.endpoint === normalize(new URL(res.url()).pathname) && !x.status); if (item) item.status = res.status(); });
  page.on('console', msg => consoleEvents.push({type:msg.type(), at:stamp()}));
  page.on('pageerror', () => pageErrors.push({type:'pageerror', at:stamp()}));
  await page.waitForTimeout(1800);
  const fail = message => { throw new Error(message); };
  const requireVisible = async (locator, message) => {
    if (!(await locator.count())) fail(message);
    try { await locator.first().waitFor({state:'visible', timeout:5000}); }
    catch { fail(message); }
    return locator.first();
  };
  const requireExactText = async (locator, expected, message) => {
    const element = await requireVisible(locator, message);
    if ((await element.textContent()).trim() !== expected) fail(message);
    return element;
  };
  const requireOption = async (select, expected, message) => {
    const option = select.locator('option').filter({hasText:expected});
    if ((await option.count()) !== 1 || (await option.first().textContent()).trim() !== expected) fail(message);
    return option.first();
  };
  const collect = async (name, target) => {
    const start = requests.length;
    await (await requireVisible(target, name+' navigation target missing')).click(); await page.waitForTimeout(900);
    const observed=requests.slice(start);
    const creates=observed.filter(x=>x.creates);
    if(creates.length) fail(name+' navigation created data: '+JSON.stringify(creates));
    return {name, requests:observed, create_requests:creates, console_errors:consoleEvents.filter(x=>x.type==='error'), page_errors:pageErrors};
  };
  const work = await collect('open_work', page.getByTitle('C\u00f4ng vi\u1ec7c', {exact:true}));
  await requireVisible(page.locator('.work-hub'), 'Work surface did not render after navigation');
  const gyo = await collect('open_gyo', page.getByTitle('Tr\u1ee3 l\u00fd GYO', {exact:true}));
  if (gyo.console_errors.length || gyo.page_errors.length) fail('GYO navigation emitted browser errors');
  const workSelect = page.locator('#assistant-work');
  await requireVisible(workSelect, 'GYO Work selector missing');
  await workSelect.selectOption('$($workA.id)'); await page.waitForTimeout(350);
  await requireExactText(page.locator('.assistant-brief strong').first(), 'C\u00f4ng vi\u1ec7c: gate1-work-a', 'GYO did not show the selected Work A');
  const threadSelect = page.getByRole('combobox', {name:'Phi\u00ean trao \u0111\u1ed5i tr\u1ee3 l\u00fd', exact:true});
  await requireVisible(threadSelect, 'GYO thread selector missing');
  await requireOption(threadSelect, 'G1-GYO-A', 'Work A GYO history is not visible');
  if (await threadSelect.locator('option').filter({hasText:'G1-GYO-B'}).count()) fail('Work B GYO history leaked into Work A');
  await threadSelect.selectOption({label:'G1-GYO-A'}); await page.waitForTimeout(350);
  if ((await threadSelect.inputValue()) !== '$($threadA.id)') fail('GYO selected history identity did not render');
  const gyoScreenshot = await page.screenshot({type:'png', encoding:'base64', fullPage:true});
  await (await requireVisible(page.getByRole('button', {name:'M\u1edf C\u00f4ng vi\u1ec7c', exact:true}), 'Open selected Work button missing')).click(); await page.waitForTimeout(500);
  await requireExactText(page.locator('.work-hub-header h1'), 'gate1-work-a', 'Work A heading did not render');
  await (await requireVisible(page.getByRole('button', {name:'Trao \u0111\u1ed5i', exact:true}), 'Work Conversation tab missing')).click(); await page.waitForTimeout(500);
  await requireVisible(page.locator('.conversation-list-item > strong').filter({hasText:'G1-WC-A'}), 'Work A Conversation identity is not visible');
  await requireVisible(page.locator('[aria-label="Trao \u0111\u1ed5i: G1-WC-A"]'), 'Work A Conversation workspace did not render');
  await requireVisible(page.getByText('G1-WC-MARKER-A', {exact:true}), 'Work A Conversation marker is not visible');
  if (await page.getByText('G1-GYO-A', {exact:true}).count()) fail('GYO history identity leaked into Work Conversation UI');
  const workScreenshot = await page.screenshot({type:'png', encoding:'base64', fullPage:true});
  await (await requireVisible(page.getByTitle('Tr\u1ee3 l\u00fd GYO', {exact:true}), 'GYO navigation target missing after Work check')).click(); await page.waitForTimeout(500);
  await workSelect.selectOption('$($workB.id)'); await page.waitForTimeout(350);
  await requireExactText(page.locator('.assistant-brief strong').first(), 'C\u00f4ng vi\u1ec7c: gate1-work-b', 'GYO did not show the selected Work B');
  await requireOption(threadSelect, 'G1-GYO-B', 'Work B GYO history is not visible');
  if (await threadSelect.locator('option').filter({hasText:'G1-GYO-A'}).count()) fail('Work A GYO history leaked into Work B');
  await (await requireVisible(page.getByRole('button', {name:'M\u1edf C\u00f4ng vi\u1ec7c', exact:true}), 'Open Work B button missing')).click(); await page.waitForTimeout(500);
  await requireExactText(page.locator('.work-hub-header h1'), 'gate1-work-b', 'Work B heading did not render');
  await (await requireVisible(page.getByRole('button', {name:'Trao \u0111\u1ed5i', exact:true}), 'Work B Conversation tab missing')).click(); await page.waitForTimeout(500);
  await requireVisible(page.locator('.conversation-list-item > strong').filter({hasText:'G1-WC-B'}), 'Work B Conversation identity is not visible');
  await requireVisible(page.getByText('G1-WC-MARKER-B', {exact:true}), 'Work B Conversation marker is not visible');
  if (await page.getByText('G1-WC-MARKER-A', {exact:true}).count()) fail('Work A Conversation marker leaked into Work B');
  const timeline = {work_conversation_ui:true, gyo_history_ui:true, selected_work_ui:true, histories_have_distinct_visible_identity:true, cross_work_history_leak:false};
  return JSON.stringify({work,gyo,timeline,work_screenshot:workScreenshot,gyo_screenshot:gyoScreenshot,network:requests,console_summary:{errors:consoleEvents.filter(x=>x.type==='error'),page_errors:pageErrors}});
}
"@
    $codePath = Join-Path $EvidenceRoot 'gate1-scenario.js'
    $code | Set-Content -Encoding utf8 -Path $codePath
    $result = Invoke-Cli @('run-code','--filename',$codePath) 'playwright-run.log'
    # playwright-cli prints the returned JSON as an escaped JSON string below
    # its "### Result" marker, so decode it twice.
    $jsonLine = ($result | Where-Object { $_ -is [string] -and $_.Trim().StartsWith('"{') } | Select-Object -Last 1)
    if (-not $jsonLine) { throw 'Playwright did not return scenario JSON.' }
    $scenario = ($jsonLine | ConvertFrom-Json) | ConvertFrom-Json
    $networkPath = Join-Path $EvidenceRoot 'network-summary-redacted.json'
    $networkRows = @($scenario.network | Select-Object method,endpoint,status,at)
    if ($networkRows.Count -eq 0) { Set-Content -Encoding utf8 -Path $networkPath -Value '[]' }
    else { $networkRows | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 -Path $networkPath }
    $scenario.console_summary | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 -Path (Join-Path $EvidenceRoot 'console-summary-redacted.json')
    [System.IO.File]::WriteAllBytes((Join-Path $EvidenceRoot '01-work-open.png'), [byte[]]$scenario.work_screenshot.data)
    [System.IO.File]::WriteAllBytes((Join-Path $EvidenceRoot '02-gyo-open.png'), [byte[]]$scenario.gyo_screenshot.data)
    $workSummary = $scenario.work | Select-Object name,requests,create_requests,console_errors,page_errors
    $gyoSummary = $scenario.gyo | Select-Object name,requests,create_requests,console_errors,page_errors
    $workSummary, $gyoSummary, $scenario.timeline | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 -Path (Join-Path $EvidenceRoot 'assertion-summary-redacted.json')
    $metadata.status = 'PASS'; $metadata.completed_at = (Get-Date).ToString('o')
    $metadata.checks = @('open Work: no POST create conversation/thread/turn','open GYO: no POST create conversation/thread/turn and no console error','UI: selected Work, Work Conversation marker, and unbound GYO history identity render separately','UI: switching Work hides the other Work history; API seed isolation reports zero cross-Work records')
    Save-Metadata
    Write-Output $EvidenceRoot
} catch {
    $metadata.status = 'FAIL'; $metadata.completed_at = (Get-Date).ToString('o'); $metadata.error = $_.Exception.Message; Save-Metadata
    throw
} finally {
    try { Invoke-Cli @('close') 'playwright-close.log' | Out-Null } catch { }
    if ($frontend -and -not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force }
    if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force }
}
