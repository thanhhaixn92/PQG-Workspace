[CmdletBinding()]
param(
    [string]$EvidenceRoot,
    [int]$BackendPort = 0,
    [int]$FrontendPort = 0,
    [switch]$GSynthetic,
    [ValidateRange(5, 120)][int]$ReadinessTimeoutSec = 30
)

# Package F native Browser support only.  It starts a disposable loopback
# fixture and deliberately never launches or controls a browser/provider.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$evidenceBase = [System.IO.Path]::GetFullPath((Join-Path $repo 'output\playwright'))
if (-not $EvidenceRoot) { $EvidenceRoot = Join-Path $evidenceBase "package-f-native-$stamp" }
$EvidenceRoot = [System.IO.Path]::GetFullPath($EvidenceRoot)
$prefix = $evidenceBase.TrimEnd('\') + '\'
if (-not $EvidenceRoot.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'EvidenceRoot must be beneath output/playwright.' }
if (-not (Split-Path -Leaf $EvidenceRoot).StartsWith('package-f-native-', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'EvidenceRoot leaf must start with package-f-native-.' }
if (Test-Path -LiteralPath $EvidenceRoot) { throw 'EvidenceRoot already exists and will not be reused.' }
New-Item -ItemType Directory -Path $EvidenceRoot -Force | Out-Null

function Get-FreePort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    try { $listener.Start(); return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}
if ($BackendPort -eq 0) { $BackendPort = Get-FreePort }
if ($FrontendPort -eq 0) { $FrontendPort = Get-FreePort }
if ($BackendPort -eq $FrontendPort) { throw 'BackendPort and FrontendPort must differ.' }

$runId = [guid]::NewGuid().ToString('N')
$tempRoot = Join-Path $env:TEMP "pqg-package-f-native-$stamp"
New-Item -ItemType Directory -Path $tempRoot, (Join-Path $tempRoot 'workspace') -Force | Out-Null
$metadataPath = Join-Path $EvidenceRoot 'run-metadata.json'
$metadata = [ordered]@{
    schema_version = 1; package = 'F'; support_route = 'native-browser-computer-use'
    run_id = $runId; source_fingerprint_sha256 = $null; status = 'STARTING'; started_at = (Get-Date).ToString('o'); completed_at = $null
    evidence_root = $EvidenceRoot; planned_assertion_count = 14; passed_assertion_count = 0
    isolation = @{ database='temporary DB_PATH beneath %TEMP%'; workspace='temporary DEFAULT_WORKSPACE_ROOT beneath %TEMP%'; ports='ephemeral loopback only'; provider='disabled: no run endpoint may reach a provider'; browser='not launched or controlled by this script'; credentials='not read or written' }
    ports = @{ backend=$BackendPort; frontend=$FrontendPort }; urls = @{ backend="http://127.0.0.1:$BackendPort"; frontend="http://127.0.0.1:$FrontendPort" }
    fixture = $null; launch = @{}; readiness = @{ status='NOT_STARTED'; attempts=0; timeout_seconds=$ReadinessTimeoutSec }
    browser_uat = @{ status='NOT_RUN'; evidence_required=@('f01-tablet-dark.jpg','f02-tablet-light.jpg','f03-mobile-light.jpg','f04-desktop-light.jpg','f05-mobile-reduced-focus.jpg','f06-keyboard-drawer.jpg','f07-reflow.jpg','f08-populated.jpg','f09-running.jpg','f10-cancelled.jpg','f11-409.jpg','f12-offline.jpg','f13-pending-approval.jpg','browser-console-redacted.json','browser-network-redacted.json','source-manifest.json','native-fidelity-manifest.json','generated-package-f-native-harness.py'); native_zoom_optional_evidence=@('f14-native-zoom.jpg','browser-native-zoom-redacted.json'); native_zoom_assertion='F14 PASS requires current-run native Chrome 200 percent evidence; otherwise NOT_RUN makes the package PARTIAL.' }
    cleanup = $null
}
function Save-Metadata { $metadata | ConvertTo-Json -Depth 16 | Set-Content -Encoding utf8 -LiteralPath $metadataPath }
function Start-Recorded([string]$Name, [string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory) {
    $stdout = Join-Path $EvidenceRoot "$Name.stdout.log"; $stderr = Join-Path $EvidenceRoot "$Name.stderr.log"
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    $metadata.launch[$Name] = @{ pid=$process.Id; start_time=$process.StartTime.ToString('o'); command="$FilePath $($Arguments -join ' ')"; stdout_log=$stdout; stderr_log=$stderr; exited=$false }
    Save-Metadata; return $process
}
function Wait-Ready($Backend, $Frontend) {
    $deadline = (Get-Date).AddSeconds($ReadinessTimeoutSec); $metadata.readiness.status = 'WAITING'
    while ((Get-Date) -lt $deadline) {
        $metadata.readiness.attempts++
        $Backend.Refresh(); $Frontend.Refresh()
        if ($Backend.HasExited -or $Frontend.HasExited) { throw 'Package F support service exited before readiness.' }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSec 2
            $page = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -UseBasicParsing -TimeoutSec 2
            if ($health.status -eq 'ok' -and $page.StatusCode -eq 200) { $metadata.readiness.status='READY'; Save-Metadata; return }
        } catch { }
        Start-Sleep -Milliseconds 250
    }
    throw 'Package F support services did not become ready within the configured timeout.'
}
function Test-LoopbackPortOpen([int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $pending = $client.BeginConnect([System.Net.IPAddress]::Loopback, $Port, $null, $null)
        if (-not $pending.AsyncWaitHandle.WaitOne(1000)) { return $false }
        $client.EndConnect($pending)
        return $true
    } catch { return $false }
    finally { $client.Dispose() }
}
function Set-ListenerMetadata([string]$Name, [int]$ListenerPid, [string]$IdentityRunId = $null, [string]$IdentityFingerprint = $null) {
    $listener = Get-Process -Id $ListenerPid -ErrorAction Stop
    $metadata.launch.$Name.listener_pid = $listener.Id
    $metadata.launch.$Name.listener_start_time = $listener.StartTime.ToString('o')
    $metadata.launch.$Name.listener_identity_run_id = $IdentityRunId
    $metadata.launch.$Name.listener_identity_source_fingerprint_sha256 = $IdentityFingerprint
    Save-Metadata
}
function Invoke-Local([string]$Method,[string]$Path,$Body=$null){$p=@{Uri="http://127.0.0.1:$BackendPort$Path";Method=$Method;ContentType='application/json';TimeoutSec=15};if($null-ne$Body){$p.Body=$Body|ConvertTo-Json -Depth 8 -Compress};Invoke-RestMethod @p}

$sourcePaths = @('scripts\start-package-f-native-fidelity.ps1','scripts\finalize-package-f-native-fidelity.ps1','scripts\stop-package-f-native-fidelity.ps1','backend\app\db\migrations.py','backend\app\main.py','backend\app\api\assistant.py','backend\app\api\action_packages.py','backend\app\api\approvals.py','backend\app\api\works.py','frontend\src\App.tsx','frontend\src\store\store.ts','frontend\src\components\AssistantChatSidebar.tsx','frontend\src\components\WorkHub.tsx','frontend\src\components\ApprovalModal.tsx','frontend\src\components\ActionPackagesPanel.tsx','frontend\src\components\ReviewInboxPanel.tsx','frontend\src\components\assistant\TurnPartRenderer.tsx','frontend\src\assistant\threadStreamRegistry.ts','frontend\src\api\assistant.ts','frontend\src\api\actionPackages.ts','frontend\src\api\approvals.ts','frontend\src\index.css')
$sourcePaths += 'scripts\finalize-package-g-synthetic.ps1'
$sourceRecords = foreach ($relative in $sourcePaths) { $full = Join-Path $repo $relative; if (-not (Test-Path -LiteralPath $full)) { throw "Required source file is missing: $relative" }; @{ path=$relative; sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $full).Hash.ToLowerInvariant() } }
$sourceFingerprintInput = (($sourceRecords | Sort-Object path | ForEach-Object { "$($_.path):$($_.sha256)" }) -join "`n")
$sourceFingerprintBytes = [Text.Encoding]::UTF8.GetBytes($sourceFingerprintInput)
$sourceFingerprintHasher = [Security.Cryptography.SHA256]::Create()
try { $sourceFingerprint = ($sourceFingerprintHasher.ComputeHash($sourceFingerprintBytes) | ForEach-Object { $_.ToString('x2') }) -join '' }
finally { $sourceFingerprintHasher.Dispose() }
$metadata.source_fingerprint_sha256 = $sourceFingerprint
$sourceManifest = @{ run_id=$runId; generated_at=(Get-Date).ToString('o'); source_fingerprint_sha256=$sourceFingerprint; files=$sourceRecords }
$sourceManifestPath = Join-Path $EvidenceRoot 'source-manifest.json'
$sourceManifest | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 -LiteralPath $sourceManifestPath
$sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourceManifestPath).Hash.ToLowerInvariant()
@{ at=(Get-Date).ToString('o'); run_id=$runId; filename='source-manifest.json'; sha256=$sourceHash; byte_count=(Get-Item -LiteralPath $sourceManifestPath).Length } | ConvertTo-Json -Compress | Add-Content -Encoding utf8 -LiteralPath (Join-Path $EvidenceRoot 'native-artifact-manifest.jsonl')

$manifest = @{ schema_version=3; package='F'; route='native-browser-computer-use'; run_id=$runId; assertion_count=14; browser_javascript_injection='prohibited'; assertions=@(
    @{id='F01';screenshot='f01-tablet-dark.jpg';width=1024;height=600;theme='dark';state='baseline';reduced_motion=$false;focus_visible=$false;drawer_opened=$false;escape_restored=$false;overflow=$false},
    @{id='F02';screenshot='f02-tablet-light.jpg';width=1024;height=600;theme='light';state='baseline';reduced_motion=$false;focus_visible=$false;drawer_opened=$false;escape_restored=$false;overflow=$false},
    @{id='F03';screenshot='f03-mobile-light.jpg';width=390;height=667;theme='light';state='baseline';reduced_motion=$false;focus_visible=$false;drawer_opened=$false;escape_restored=$false;overflow=$false},
    @{id='F04';screenshot='f04-desktop-light.jpg';width=1440;height=900;theme='light';state='baseline';reduced_motion=$false;focus_visible=$false;drawer_opened=$false;escape_restored=$false;overflow=$false},
    @{id='F05';screenshot='f05-mobile-reduced-focus.jpg';width=390;height=667;theme='dark';state='reduced-motion-focus';reduced_motion=$true;focus_visible=$true;drawer_opened=$false;escape_restored=$false;overflow=$false},
    @{id='F06';screenshot='f06-keyboard-drawer.jpg';width=390;height=667;theme='dark';state='keyboard-drawer';reduced_motion=$false;focus_visible=$true;drawer_opened=$true;escape_restored=$true;overflow=$false},
    @{id='F07';screenshot='f07-reflow.jpg';width=320;height=640;theme='dark';state='reflow';reduced_motion=$false;focus_visible=$false;drawer_opened=$false;escape_restored=$false;overflow=$false},
    @{id='F08';screenshot='f08-populated.jpg';width=1440;height=900;theme='light';state='populated';reduced_motion=$false;focus_visible=$false;drawer_opened=$false;escape_restored=$false;overflow=$false},
    @{id='F09';screenshot='f09-running.jpg';width=1440;height=900;theme='light';state='running';reduced_motion=$false;focus_visible=$false;drawer_opened=$false;escape_restored=$false;overflow=$false},
    @{id='F10';screenshot='f10-cancelled.jpg';width=1440;height=900;theme='light';state='cancelled';reduced_motion=$false;focus_visible=$false;drawer_opened=$false;escape_restored=$false;overflow=$false},
    @{id='F11';screenshot='f11-409.jpg';width=1440;height=900;theme='light';state='scope-409';reduced_motion=$false;focus_visible=$false;drawer_opened=$false;escape_restored=$false;overflow=$false},
    @{id='F12';screenshot='f12-offline.jpg';width=1440;height=900;theme='light';state='offline-retry';reduced_motion=$false;focus_visible=$false;drawer_opened=$false;escape_restored=$false;overflow=$false},
    @{id='F13';screenshot='f13-pending-approval.jpg';width=1440;height=900;theme='light';state='pending-action-package-visual-only';reduced_motion=$false;focus_visible=$false;drawer_opened=$false;escape_restored=$false;overflow=$false},
    @{id='F14';screenshot='f14-native-zoom.jpg';width=1440;height=900;theme='native';state='native-zoom';reduced_motion=$false;focus_visible=$false;drawer_opened=$false;escape_restored=$false;overflow=$false}
) }
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 -LiteralPath (Join-Path $EvidenceRoot 'native-fidelity-manifest.json')
$nativeManifestPath = Join-Path $EvidenceRoot 'native-fidelity-manifest.json'
$nativeManifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $nativeManifestPath).Hash.ToLowerInvariant()
@{ at=(Get-Date).ToString('o'); run_id=$runId; filename='native-fidelity-manifest.json'; sha256=$nativeManifestHash; byte_count=(Get-Item -LiteralPath $nativeManifestPath).Length } | ConvertTo-Json -Compress | Add-Content -Encoding utf8 -LiteralPath (Join-Path $EvidenceRoot 'native-artifact-manifest.jsonl')

$harnessPath = Join-Path $tempRoot 'package_f_native_harness.py'
@'
import hashlib, json, os, re, time, uuid
from pathlib import Path
import aiosqlite
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from app.main import create_app

app = create_app()
ALLOWED = {'f01-tablet-dark.jpg','f02-tablet-light.jpg','f03-mobile-light.jpg','f04-desktop-light.jpg','f05-mobile-reduced-focus.jpg','f06-keyboard-drawer.jpg','f07-reflow.jpg','f08-populated.jpg','f09-running.jpg','f10-cancelled.jpg','f11-409.jpg','f12-offline.jpg','f13-pending-approval.jpg','f14-native-zoom.jpg','browser-console-redacted.json','browser-network-redacted.json','browser-native-zoom-redacted.json'}
EXPECTED = {
    'F01':('f01-tablet-dark.jpg',1024,600,'dark','baseline',False,False,False,False,False),
    'F02':('f02-tablet-light.jpg',1024,600,'light','baseline',False,False,False,False,False),
    'F03':('f03-mobile-light.jpg',390,667,'light','baseline',False,False,False,False,False),
    'F04':('f04-desktop-light.jpg',1440,900,'light','baseline',False,False,False,False,False),
    'F05':('f05-mobile-reduced-focus.jpg',390,667,'dark','reduced-motion-focus',True,True,False,False,False),
    'F06':('f06-keyboard-drawer.jpg',390,667,'dark','keyboard-drawer',False,True,True,True,False),
    'F07':('f07-reflow.jpg',320,640,'dark','reflow',False,False,False,False,False),
    'F08':('f08-populated.jpg',1440,900,'light','populated',False,False,False,False,False),
    'F09':('f09-running.jpg',1440,900,'light','running',False,False,False,False,False),
    'F10':('f10-cancelled.jpg',1440,900,'light','cancelled',False,False,False,False,False),
    'F11':('f11-409.jpg',1440,900,'light','scope-409',False,False,False,False,False),
    'F12':('f12-offline.jpg',1440,900,'light','offline-retry',False,False,False,False,False),
    'F13':('f13-pending-approval.jpg',1440,900,'light','pending-action-package-visual-only',False,False,False,False,False),
    'F14':('f14-native-zoom.jpg',1440,900,'native','native-zoom',False,False,False,False,False),
}
g_synthetic = os.environ.get('PACKAGE_F_G_SYNTHETIC') == '1'
observations = {'product_posts': {}, 'run_posts': 0, 'controlled_409': 0, 'controlled_503': 0, 'controlled_synthetic_sample': 0, 'offline': False, 'offline_history': [], 'browser_action_mutations': 0, 'browser_approval_decisions': 0, 'executor_runs': 0, 'fixture': {}, 'completed_assertions': {}, 'g_offline_once': False}
def root(): return Path(os.environ['PACKAGE_F_EVIDENCE_ROOT'])
def db(): return os.environ['DB_PATH']
def safe(value):
    if value and not value.startswith('PACKAGE-F-'): raise HTTPException(status_code=422, detail='Package F fixture values must be synthetic.')

@app.get('/_package_f/identity')
async def identity():
    return {'run_id': os.environ['PACKAGE_F_RUN_ID'], 'pid': os.getpid(), 'source_fingerprint_sha256': os.environ['PACKAGE_F_SOURCE_FINGERPRINT'], 'g_synthetic': g_synthetic}

@app.middleware('http')
async def intercept_409(request: Request, call_next):
    path = request.url.path
    if request.method == 'POST' and path.startswith('/api/'):
        observations['product_posts'][path] = observations['product_posts'].get(path, 0) + 1
        if re.fullmatch(r'/api/assistant/threads/[^/]+/(?:runs|turns)', path): observations['run_posts'] += 1
        if '/action-packages' in path: observations['browser_action_mutations'] = observations.get('browser_action_mutations', 0) + 1
        if re.fullmatch(r'/api/approvals/[^/]+', path): observations['browser_approval_decisions'] += 1
        if any(token in path for token in ('/execute','/executor')): observations['executor_runs'] = observations.get('executor_runs', 0) + 1
    if request.method == 'POST' and re.fullmatch(r'/api/assistant/threads/[^/]+/(?:runs|turns)', request.url.path):
        body = await request.body()
        try: payload = json.loads(body.decode('utf-8'))
        except Exception: payload = {}
        if payload.get('prompt') == 'PACKAGE-F-409-SCOPE':
            observations['controlled_409'] += 1
            return JSONResponse(status_code=409, content={'detail':'PACKAGE-F controlled scope/run conflict'})
        if g_synthetic and payload.get('prompt') == 'PACKAGE-G-SAMPLE':
            observations['controlled_synthetic_sample'] += 1
        if g_synthetic and payload.get('prompt') == 'PACKAGE-G-OFFLINE' and not observations['g_offline_once']:
            observations['g_offline_once'] = True
            observations['controlled_503'] += 1
            return JSONResponse(status_code=503, content={'detail':'PACKAGE-G controlled offline fixture'})
    if observations['offline'] and path.startswith('/api/') and not path.startswith('/api/health'):
        return JSONResponse(status_code=503, content={'detail':'PACKAGE-F controlled offline fixture'})
    return await call_next(request)

class Seed(BaseModel):
    thread_id: str; work_id: str; conversation_id: str; state: str = Field(pattern='^(running|cancelled|completed)$'); marker: str
class Artifact(BaseModel):
    run_id: str = Field(min_length=32,max_length=32); filename: str; sha256: str = Field(pattern='^[0-9a-f]{64}$'); data_base64: str = Field(min_length=1)
class SeedApproval(BaseModel):
    work_id: str; conversation_id: str
class Receipt(BaseModel):
    assertion_id: str = Field(pattern=r'^F(?:0[1-9]|1[0-4])$'); status: str = Field(pattern='^(PASS|FAIL|NOT_RUN)$'); run_id: str = Field(min_length=32,max_length=32); evidence: list[str] = Field(min_length=1); artifact_hashes: dict[str,str] = Field(min_length=1); cell_id: str; viewport: dict[str,int]; theme: str = Field(pattern='^(dark|light|native)$'); state: str; reduced_motion: bool; focus_target: str; overflow: bool; source_manifest_sha: str = Field(pattern='^[0-9a-f]{64}$'); capture_width: int = Field(gt=0); capture_height: int = Field(gt=0); device_pixel_ratio: float = Field(gt=0); client_width: int = Field(gt=0); scroll_width: int = Field(gt=0); focus_visible: bool; drawer_opened: bool; escape_restored: bool; offline_enabled_observed: bool; retry_recovered: bool; controlled_409_count: int = Field(ge=0); prompt_preserved: bool; native_zoom_percent: int | None = None; browser_version: str | None = None; browser_profile: str | None = None

@app.post('/_package_f/seed-turn')
async def seed_turn(seed: Seed):
    safe(seed.marker); turn_id='package-f-turn-'+uuid.uuid4().hex; now=int(time.time())
    status=seed.state; error='PACKAGE-F-SYNTHETIC-CANCELLED' if status == 'cancelled' else None
    completed=now if status in {'cancelled','completed'} else None
    async with aiosqlite.connect(db()) as conn:
        await conn.execute("INSERT INTO assistant_turns (id,thread_id,work_id,conversation_id,role,status,model_id,created_at,completed_at,error) VALUES (?,?,?,?, 'assistant', ?, 'package-f-synthetic', ?,?,?)",(turn_id,seed.thread_id,seed.work_id,seed.conversation_id,status,now,completed,error))
        await conn.execute("INSERT INTO assistant_turn_parts (id,turn_id,part_type,content_json,sort_order,created_at) VALUES (?,?, 'text', ?,0,?)",(uuid.uuid4().hex,turn_id,json.dumps({'text':seed.marker}),now))
        await conn.commit()
    return {'turn_id':turn_id}

@app.post('/_package_f/seed-pending-approval')
async def seed_pending_approval(seed: SeedApproval):
    if observations['fixture']: raise HTTPException(status_code=409,detail='PACKAGE-F pending fixture is immutable and may be seeded only once')
    if not g_synthetic and 'F12' not in observations['completed_assertions']: raise HTTPException(status_code=409,detail='PACKAGE-F pending fixture may be seeded only after validated F12 recovery')
    now=int(time.time()); package_id='package-f-action-'+uuid.uuid4().hex; approval_id=None if g_synthetic else 'package-f-approval-'+uuid.uuid4().hex
    async with aiosqlite.connect(db()) as conn:
        await conn.execute("INSERT INTO action_packages (id,session_id,conversation_id,title,description,package_hash,status,created_at,updated_at) VALUES (?,?,?,?,?,?, 'awaiting_approval',?,?)",(package_id,seed.work_id,seed.conversation_id,'PACKAGE-F-PENDING-APPROVAL','Synthetic visual fidelity only; not real E2.',hashlib.sha256(package_id.encode()).hexdigest(),now,now))
        await conn.execute("INSERT INTO action_steps (id,package_id,sort_order,kind,risk_level,input_json,status,created_at,updated_at) VALUES (?,?,0,'work_plan_step_update','write','{}','pending',?,?)",('package-f-step-'+uuid.uuid4().hex,package_id,now,now))
        if approval_id:
            await conn.execute("INSERT INTO approval_requests (id,session_id,action,target,risk_level,description,status,created_at,expires_at) VALUES (?,?,?,?,? ,?,'pending',?,?)",(approval_id,seed.work_id,'PACKAGE-F-SYNTHETIC-PROPOSAL',package_id,'write','Synthetic fixture only; do not approve or execute.',now,now+3600))
        await conn.commit()
    observations['fixture'] = {'package_id':package_id,'approval_id':approval_id,'seeded_at':int(time.time()),'after_f12_recorded_at':observations['completed_assertions'].get('F12'),'synthetic_g':g_synthetic}
    return {'package_id':package_id,'approval_id':approval_id}

@app.get('/_package_f/observe')
async def observe():
    result={'provider_bound_run_attempts':max(observations['run_posts']-observations['controlled_409']-observations['controlled_503']-observations['controlled_synthetic_sample'],0),'controlled_409':observations['controlled_409'],'controlled_503':observations['controlled_503'],'controlled_synthetic_sample':observations['controlled_synthetic_sample'],'product_posts':dict(observations['product_posts']),'offline_history':list(observations['offline_history']),'fixture_seeded_action_packages':0,'fixture_seeded_approvals':0,'browser_action_mutations':observations.get('browser_action_mutations',0),'browser_approval_decisions':observations.get('browser_approval_decisions',0),'executor_runs':observations.get('executor_runs',0),'synthetic_turns':0,'fixture':{},'completed_assertions':dict(observations['completed_assertions'])}
    async with aiosqlite.connect(db()) as conn:
        async with conn.execute("SELECT COUNT(*) FROM assistant_turns WHERE model_id='package-f-synthetic'") as cur: result['synthetic_turns']=(await cur.fetchone())[0]
        fixture=observations['fixture']
        if fixture:
            async with conn.execute("SELECT status,title FROM action_packages WHERE id=?",(fixture['package_id'],)) as cur: package=await cur.fetchone()
            async with conn.execute("SELECT COUNT(*) FROM action_steps WHERE package_id=? AND status='pending'",(fixture['package_id'],)) as cur: steps=(await cur.fetchone())[0]
            approval=None
            if fixture['approval_id']:
                async with conn.execute("SELECT status,target FROM approval_requests WHERE id=?",(fixture['approval_id'],)) as cur: approval=await cur.fetchone()
            result['fixture_seeded_action_packages']=1 if package else 0; result['fixture_seeded_approvals']=1 if approval else 0
            result['fixture']={'package_id':fixture['package_id'],'package_status':package[0] if package else None,'package_title':package[1] if package else None,'pending_step_count':steps,'approval_id':fixture['approval_id'],'approval_status':approval[0] if approval else None,'approval_target':approval[1] if approval else None,'seeded_at':fixture['seeded_at'],'after_f12_recorded_at':fixture['after_f12_recorded_at']}
    return result

@app.post('/_package_f/control/offline')
async def controlled_offline(enabled: bool):
    observations['offline'] = enabled
    observations['offline_history'].append({'enabled':enabled,'at':int(time.time())})
    return {'offline': enabled}

@app.post('/_package_f/evidence/artifact')
async def artifact(item: Artifact):
    if item.run_id != os.environ['PACKAGE_F_RUN_ID']: raise HTTPException(status_code=409,detail='Package F run identity mismatch')
    if item.filename not in ALLOWED or Path(item.filename).name != item.filename: raise HTTPException(status_code=422,detail='Artifact name is not allowed')
    import base64
    try: data=base64.b64decode(item.data_base64,validate=True)
    except Exception as error: raise HTTPException(status_code=422,detail='Artifact is not valid base64') from error
    if hashlib.sha256(data).hexdigest()!=item.sha256: raise HTTPException(status_code=422,detail='Artifact SHA-256 mismatch')
    target=root()/item.filename
    if target.exists(): raise HTTPException(status_code=409,detail='Artifact filename is immutable')
    if item.filename.endswith('.jpg') and (len(data)<16 or not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9')): raise HTTPException(status_code=422,detail='Screenshot must be complete JPEG')
    if item.filename.endswith('.json'):
        try: json.loads(data.decode('utf-8'))
        except Exception as error: raise HTTPException(status_code=422,detail='JSON artifact is invalid') from error
    target.write_bytes(data)
    record={'run_id':item.run_id,'filename':item.filename,'sha256':item.sha256,'byte_count':len(data),'at':int(time.time()),'offline':observations['offline'],'controlled_409':observations['controlled_409']}
    with (root()/'native-artifact-manifest.jsonl').open('a',encoding='utf-8') as out: out.write(json.dumps(record,sort_keys=True)+'\n')
    return {'stored':item.filename}

@app.post('/_package_f/evidence/assertion')
async def receipt(item: Receipt):
    if item.run_id != os.environ['PACKAGE_F_RUN_ID']: raise HTTPException(status_code=409,detail='Package F run identity mismatch')
    expected=EXPECTED[item.assertion_id]
    screenshot,width,height,theme,state,reduced,focus_visible,drawer_opened,escape_restored,overflow=expected
    if item.assertion_id == 'F14' and item.status == 'PASS' and (item.native_zoom_percent != 200 or not item.browser_version or not item.browser_profile or 'browser-native-zoom-redacted.json' not in item.evidence): raise HTTPException(status_code=422,detail='F14 PASS requires native 200 percent zoom, browser version, profile and native zoom evidence')
    if item.assertion_id != 'F14' and item.status != 'PASS': raise HTTPException(status_code=422,detail='F01 through F13 must be PASS or finalizer will fail')
    if item.status == 'PASS' and screenshot not in item.evidence: raise HTTPException(status_code=422,detail='Receipt lacks its required screenshot')
    for name in item.evidence:
        if name not in ALLOWED or name not in item.artifact_hashes: raise HTTPException(status_code=422,detail='Receipt contains unapproved or unhashed evidence')
    if item.cell_id != item.assertion_id or item.viewport != {'width':width,'height':height} or item.theme != theme or item.state != state or item.reduced_motion != reduced or item.focus_visible != focus_visible or item.drawer_opened != drawer_opened or item.escape_restored != escape_restored or item.overflow != overflow: raise HTTPException(status_code=422,detail='Receipt does not match the canonical matrix cell')
    if item.assertion_id == 'F14':
        if item.client_width < 1 or item.client_width > width or item.scroll_width != item.client_width or item.capture_width != width or item.capture_height != height: raise HTTPException(status_code=422,detail='F14 native zoom geometry is invalid')
    elif item.client_width != width or item.scroll_width != width or item.capture_width != round(width*item.device_pixel_ratio) or item.capture_height != round(height*item.device_pixel_ratio):
        raise HTTPException(status_code=422,detail='Receipt geometry/reflow binding is invalid')
    if item.assertion_id == 'F05' and not item.focus_target: raise HTTPException(status_code=422,detail='F05 requires a visible focus target')
    if item.assertion_id == 'F06' and not item.focus_target: raise HTTPException(status_code=422,detail='F06 requires drawer focus restoration target')
    if item.assertion_id == 'F11' and (item.controlled_409_count < 1 or not item.prompt_preserved): raise HTTPException(status_code=422,detail='F11 requires controlled 409 and preserved prompt')
    if item.assertion_id == 'F12' and (not item.offline_enabled_observed or not item.retry_recovered or observations['offline'] or len(observations['offline_history']) < 2 or observations['offline_history'][-2]['enabled'] is not True or observations['offline_history'][-1]['enabled'] is not False): raise HTTPException(status_code=422,detail='F12 requires an offline capture followed by controlled recovery')
    recorded_at=int(time.time()); payload=item.model_dump(); payload['recorded_at']=recorded_at; payload['server_observation']={'controlled_409':observations['controlled_409'],'offline':observations['offline'],'offline_history':list(observations['offline_history']),'fixture':dict(observations['fixture']),'completed_assertions':dict(observations['completed_assertions'])}
    with (root()/'native-assertion-receipts.jsonl').open('a',encoding='utf-8') as out: out.write(json.dumps(payload,sort_keys=True)+'\n')
    observations['completed_assertions'][item.assertion_id]=recorded_at
    return {'recorded':item.assertion_id}
'@ | Set-Content -Encoding utf8 -LiteralPath $harnessPath
$harnessEvidence = Join-Path $EvidenceRoot 'generated-package-f-native-harness.py'
Copy-Item -LiteralPath $harnessPath -Destination $harnessEvidence -ErrorAction Stop
$harnessHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $harnessEvidence).Hash.ToLowerInvariant()
@{ at=(Get-Date).ToString('o'); run_id=$runId; filename='generated-package-f-native-harness.py'; sha256=$harnessHash; byte_count=(Get-Item -LiteralPath $harnessEvidence).Length } | ConvertTo-Json -Compress | Add-Content -Encoding utf8 -LiteralPath (Join-Path $EvidenceRoot 'native-artifact-manifest.jsonl')

$launcherPath = Join-Path $tempRoot 'package_f_native_vite_launcher.mjs'
@'
import { pathToFileURL } from 'node:url';
const [frontendRoot, backendPort, frontendPort, viteModulePath, reactPluginPath] = process.argv.slice(2);
const { createServer } = await import(pathToFileURL(viteModulePath).href);
const react = await import(pathToFileURL(reactPluginPath).href);
const target=`http://127.0.0.1:${backendPort}`;
const server=await createServer({root:frontendRoot,configFile:false,plugins:[react.default()],server:{host:'127.0.0.1',port:Number(frontendPort),strictPort:true,proxy:{'/api/health':{target,rewrite:p=>p.replace(/^\/api/,'')},'/api':target}}});
await server.listen();
const close=async()=>{await server.close();process.exit(0)}; process.once('SIGINT',close);process.once('SIGTERM',close);
'@ | Set-Content -Encoding utf8 -LiteralPath $launcherPath

$backend = $null; $frontend = $null
try {
    $env:DB_PATH = Join-Path $tempRoot 'app.db'; $env:DEFAULT_WORKSPACE_ROOT = Join-Path $tempRoot 'workspace'; $env:CORS_ORIGINS="http://127.0.0.1:$FrontendPort"; $env:HERMES_DEV_MOCK='1'; $env:OUTBOX_DISPATCHER_ENABLED='0'; $env:PACKAGE_F_EVIDENCE_ROOT=$EvidenceRoot; $env:PACKAGE_F_RUN_ID=$runId; $env:PACKAGE_F_SOURCE_FINGERPRINT=$sourceFingerprint; $env:PACKAGE_F_G_SYNTHETIC=$(if($GSynthetic){'1'}else{'0'})
    $backendExe = Join-Path $repo 'backend\.venv\Scripts\python.exe'; $viteModule=Join-Path $repo 'frontend\node_modules\vite\dist\node\index.js'; $reactModule=Join-Path $repo 'frontend\node_modules\@vitejs\plugin-react\dist\index.js'
    foreach($required in @($backendExe,$viteModule,$reactModule)) { if(-not(Test-Path -LiteralPath $required)){ throw "Required local tool missing: $required" } }
    $backend=Start-Recorded 'backend' $backendExe @('-m','uvicorn','package_f_native_harness:app','--app-dir',$tempRoot,'--host','127.0.0.1','--port',"$BackendPort") (Join-Path $repo 'backend')
    $frontend=Start-Recorded 'frontend' 'node.exe' @($launcherPath,(Join-Path $repo 'frontend'),"$BackendPort","$FrontendPort",$viteModule,$reactModule) (Join-Path $repo 'frontend')
    Wait-Ready $backend $frontend
    $identity = Invoke-Local 'Get' '/_package_f/identity'
    if ($identity.run_id -ne $runId -or $identity.source_fingerprint_sha256 -ne $sourceFingerprint) { throw 'Package F backend identity did not match the current run.' }
    if (-not (Test-LoopbackPortOpen $BackendPort) -or -not (Test-LoopbackPortOpen $FrontendPort)) { throw 'Package F readiness HTTP response did not have a matching loopback listener.' }
    Set-ListenerMetadata 'backend' ([int]$identity.pid) $identity.run_id $identity.source_fingerprint_sha256
    Set-ListenerMetadata 'frontend' ([int]$frontend.Id) $runId $sourceFingerprint
    $work=Invoke-Local 'Post' '/api/sessions' @{title='PACKAGE-F-WORK';goal='Synthetic native fidelity fixture';data_scope='work_only'}
    $conversation=@(Invoke-Local 'Get' "/api/works/$($work.id)/conversations")[0]
    $conversation=Invoke-Local 'Patch' "/api/works/$($work.id)/conversations/$($conversation.id)" @{title='PACKAGE-F-CONVERSATION';purpose='Synthetic fidelity states'}
    $thread=Invoke-Local 'Post' "/api/assistant/works/$($work.id)/conversations/$($conversation.id)/assistant-thread"
    $running=Invoke-Local 'Post' '/_package_f/seed-turn' @{thread_id=$thread.id;work_id=$work.id;conversation_id=$conversation.id;state='running';marker='PACKAGE-F-RUNNING'}
    $cancelled=Invoke-Local 'Post' '/_package_f/seed-turn' @{thread_id=$thread.id;work_id=$work.id;conversation_id=$conversation.id;state='cancelled';marker='PACKAGE-F-CANCELLED'}
    $completed=$null; $pending=$null; $alternateConversation=$null; $alternateThread=$null; $alternateCompleted=$null
    if($GSynthetic){
        $completed=Invoke-Local 'Post' '/_package_f/seed-turn' @{thread_id=$thread.id;work_id=$work.id;conversation_id=$conversation.id;state='completed';marker='PACKAGE-F-G-COMPLETED'}
        $pending=Invoke-Local 'Post' '/_package_f/seed-pending-approval' @{work_id=$work.id;conversation_id=$conversation.id}
        $alternateConversation=Invoke-Local 'Post' "/api/works/$($work.id)/conversations" @{title='PACKAGE-F-G-ALTERNATE';purpose='Synthetic scope-switch timeline'}
        $alternateThread=Invoke-Local 'Post' "/api/assistant/works/$($work.id)/conversations/$($alternateConversation.id)/assistant-thread"
        $alternateCompleted=Invoke-Local 'Post' '/_package_f/seed-turn' @{thread_id=$alternateThread.id;work_id=$work.id;conversation_id=$alternateConversation.id;state='completed';marker='PACKAGE-F-G-ALTERNATE-TIMELINE'}
    }
    $baseline=Invoke-Local 'Get' '/_package_f/observe'
    $metadata.fixture=@{work=@{id=$work.id;title=$work.title};conversation=@{id=$conversation.id;title=$conversation.title};thread=@{id=$thread.id};running_turn=$running.turn_id;cancelled_turn=$cancelled.turn_id;completed_turn=if($completed){$completed.turn_id}else{$null};alternate_conversation=if($alternateConversation){@{id=$alternateConversation.id;title=$alternateConversation.title;thread_id=$alternateThread.id;completed_turn=$alternateCompleted.turn_id}}else{$null};pending_approval=if($pending){@{package_id=$pending.package_id;approval_id=$pending.approval_id;synthetic_only=$true;approval_request_seeded=$false}}else{@{seed_endpoint='/_package_f/seed-pending-approval';seed_only_after_f12=$true;synthetic_only=$true}};controlled_409_prompt='PACKAGE-F-409-SCOPE';offline_prompt=if($GSynthetic){'PACKAGE-G-OFFLINE'}else{$null};g_synthetic=[bool]$GSynthetic;baseline_observation=$baseline}
    $metadata.status='AWAITING_NATIVE_BROWSER_FIDELITY'; Save-Metadata; Write-Output $EvidenceRoot
} catch {
    $starterMessage = $_.Exception.Message
    $metadata.status='FAIL';$metadata.completed_at=(Get-Date).ToString('o');$metadata.failure=@{stage='starter';message=$starterMessage};Save-Metadata
    try { & (Join-Path $PSScriptRoot 'stop-package-f-native-fidelity.ps1') -EvidenceRoot $EvidenceRoot -PreserveTerminalStatus } catch { }
    $metadata = Get-Content -Raw -Encoding utf8 -LiteralPath $metadataPath | ConvertFrom-Json
    $metadata.failure = @{stage='starter';message=$starterMessage}
    if ($metadata.status -ne 'CLEANUP_INCOMPLETE') { $metadata.status='FAIL' }
    $metadata | ConvertTo-Json -Depth 16 | Set-Content -Encoding utf8 -LiteralPath $metadataPath
    throw
}
