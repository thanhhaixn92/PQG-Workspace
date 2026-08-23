param(
    [ValidateSet("AppShell", "PrimarySurfaces", "WorkTabs", "AsyncStates", "Accessibility")]
    [string]$Batch = "AppShell",
    [string]$EvidenceRoot = "",
    [int]$BackendPort = 0,
    [int]$FrontendPort = 0
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (-not $EvidenceRoot) { $EvidenceRoot = Join-Path $repo "output\playwright\v22-$stamp" }
$EvidenceRoot = [System.IO.Path]::GetFullPath($EvidenceRoot)
$batchSlug = $Batch.ToLowerInvariant()
$batchRoot = Join-Path $EvidenceRoot "$batchSlug-$stamp"
$tempRoot = Join-Path $env:TEMP "uat-codex-fidelity-$batchSlug-$stamp"
$metadataPath = Join-Path $batchRoot "run-metadata.json"
New-Item -ItemType Directory -Path $batchRoot -Force | Out-Null
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

function Get-FreeTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    try { $listener.Start(); return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port }
    finally { $listener.Stop() }
}
if ($BackendPort -eq 0) { $BackendPort = Get-FreeTcpPort }
if ($FrontendPort -eq 0) { $FrontendPort = Get-FreeTcpPort }
if ($BackendPort -eq $FrontendPort) { throw "BackendPort and FrontendPort must differ." }

$backend = $null
$frontend = $null
$session = "v22-$batchSlug-$stamp"
$cli = @("--yes", "--package", "@playwright/cli", "playwright-cli", "-s=$session")
$previousEnv = @{}
foreach ($name in @("DB_PATH", "DEFAULT_WORKSPACE_ROOT", "CORS_ORIGINS", "HERMES_DEV_MOCK", "OUTBOX_DISPATCHER_ENABLED", "VITE_API_BASE_URL", "VITE_API_PROXY_TARGET", "VITE_SHOW_TEST_WORKS")) {
    $previousEnv[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
$metadata = [ordered]@{
    schema_version = 2; batch = $Batch; status = "RUNNING"
    started_at = (Get-Date).ToString("o"); completed_at = $null
    evidence_root = $EvidenceRoot; batch_root = $batchRoot; temp_root = $tempRoot
    temp_data_prefix = "uat-codex-"; backend_port = $BackendPort; frontend_port = $FrontendPort
    backend_pid = $null; frontend_pid = $null; captures = @(); failures = @()
    not_run = @("browser zoom 200 percent", "five-person usability (deferred by product owner)")
}
function Save-Metadata { $metadata | ConvertTo-Json -Depth 8 | Set-Content -Path $metadataPath -Encoding utf8 }
function Invoke-Cli([string[]]$Arguments, [string]$LogName = "") {
    $output = & npx @cli @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($LogName) { $output | Set-Content -Path (Join-Path $batchRoot $LogName) -Encoding utf8 }
    if ($exitCode -ne 0) { throw "playwright-cli failed ($exitCode): $($Arguments[0])" }
    return $output
}
function Wait-Ready {
    for ($attempt = 0; $attempt -lt 80; $attempt++) {
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:$BackendPort/health" -TimeoutSec 2
            $page = Invoke-WebRequest "http://127.0.0.1:$FrontendPort" -UseBasicParsing -TimeoutSec 2
            if ($health.status -eq "ok" -and $page.StatusCode -eq 200) { return }
        } catch { Start-Sleep -Milliseconds 250 }
    }
    throw "Services did not become ready on ports $BackendPort/$FrontendPort."
}
function Add-Capture([string]$Id, [string]$State, [string]$Result = "PASS", [string]$Note = "") {
    $metadata.captures += [ordered]@{ id=$Id; state=$State; result=$Result; note=$Note; recorded_at=(Get-Date).ToString("o") }
    Save-Metadata
}
function Capture-Set(
    [string]$Id, [object[]]$Viewports, [string]$Selector = "", [string]$RequiredSelector = "",
    [string]$AssertMode = "standard", [switch]$AllowConsoleErrors
) {
    $rootJson = ConvertTo-Json (($batchRoot -replace '\\', '/')) -Compress
    $idJson = ConvertTo-Json $Id -Compress
    $selectorJson = ConvertTo-Json $Selector -Compress
    $requiredJson = ConvertTo-Json $RequiredSelector -Compress
    $viewportsJson = ConvertTo-Json -InputObject $Viewports -Compress -Depth 4
    $allowErrors = if ($AllowConsoleErrors) { "true" } else { "false" }
    $assertModeJson = ConvertTo-Json $AssertMode -Compress
    $code = @"
async (page) => {
  const id = $idJson, root = $rootJson, selector = $selectorJson, requiredSelector = $requiredJson;
  const viewports = $viewportsJson, allowConsoleErrors = $allowErrors, assertMode = $assertModeJson;
  const consoleErrors = [], pageErrors = [];
  const onConsole = msg => { if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 240)); };
  const onPageError = err => pageErrors.push(String(err).slice(0, 240));
  page.on('console', onConsole); page.on('pageerror', onPageError);
  try {
    if (selector) {
      const candidates = page.locator(selector); let clicked = false;
      for (let i = 0; i < await candidates.count(); i++) if (await candidates.nth(i).isVisible()) { await candidates.nth(i).click(); clicked = true; break; }
      if (!clicked) throw new Error('No visible navigation target for ' + selector);
      await page.waitForTimeout(350);
    }
    const results = [];
    for (const viewport of viewports) {
      await page.setViewportSize(viewport); await page.waitForTimeout(250);
      const layout = await page.evaluate(() => {
        const root = document.documentElement, body = document.body, nav = document.querySelector('.sidebar-panel');
        const rect = nav ? nav.getBoundingClientRect() : null;
        return { overflow: Math.max(root.scrollWidth, body ? body.scrollWidth : 0) > innerWidth + 1,
          scrollWidth: Math.max(root.scrollWidth, body ? body.scrollWidth : 0), innerWidth,
          nav: rect ? {width:rect.width, top:rect.top, height:rect.height} : null };
      });
      if (layout.overflow) throw new Error('Horizontal overflow at ' + viewport.width + 'x' + viewport.height);
      if (assertMode === 'appShell') {
        if (!layout.nav) throw new Error('App navigation missing');
        const expected = viewport.width <= 768 ? 'bottom' : viewport.width <= 1024 ? 'rail' : 'desktop';
        const actual = layout.nav.top > viewport.height / 2 ? 'bottom' : layout.nav.width <= 80 ? 'rail' : 'desktop';
        if (actual !== expected) throw new Error('Navigation mode ' + actual + ' expected ' + expected + ' at ' + viewport.width);
      }
      if (requiredSelector && !(await page.locator(requiredSelector).first().isVisible())) throw new Error('Required control not visible: ' + requiredSelector);
      await page.screenshot({path: root + '/' + id + '-' + viewport.width + 'x' + viewport.height + '.png', fullPage:true});
      results.push({viewport, layout});
    }
    if (!allowConsoleErrors && (consoleErrors.length || pageErrors.length)) throw new Error('Browser errors: ' + JSON.stringify({consoleErrors,pageErrors}));
    return JSON.stringify({id,results,consoleErrors,pageErrors});
  } finally { page.off('console', onConsole); page.off('pageerror', onPageError); }
}
"@
    $codePath = Join-Path $batchRoot "$Id-code.js"
    $code | Set-Content -Path $codePath -Encoding utf8
    Invoke-Cli @("run-code", "--filename", $codePath) "$Id-metrics.log" | Out-Null
    Invoke-Cli @("snapshot", "--filename", (Join-Path $batchRoot "$Id-snapshot.md"), "--boxes") "$Id-snapshot.log" | Out-Null
    Add-Capture $Id "visual/runtime"
}
function Seed-Data {
    $work = Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/sessions" -Method Post -ContentType "application/json" -Body (@{
        title="uat-codex-Công việc có tiêu đề dài để kiểm tra reflow và clipping tại breakpoint"; goal="Kiểm tra điều hướng, nội dung dài, proposal và trạng thái chờ duyệt."; data_scope="work_only"
    } | ConvertTo-Json)
    $phase = Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/works/$($work.id)/plan/phases" -Method Post -ContentType "application/json" -Body (@{title="Giai đoạn kiểm thử giao diện"} | ConvertTo-Json)
    $step = Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/works/$($work.id)/plan/steps" -Method Post -ContentType "application/json" -Body (@{phase_id=$phase.id;title="Bước dài cần người dùng xác nhận trước khi hoàn tất";description="Nội dung dài để kiểm tra xuống dòng và hành động chính vẫn nhìn thấy.";status="in_progress"} | ConvertTo-Json)
    $conversation = Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/works/$($work.id)/conversations" -Method Post -ContentType "application/json" -Body (@{title="uat-codex-Trao đổi chính"} | ConvertTo-Json)
    $packageBody = @{title="Đề xuất cập nhật bước";description="Gói đang chờ duyệt để kiểm tra trạng thái approval.";conversation_id=$conversation.id;steps=@(@{kind="work_plan_step_update";input=@{step_id=$step.id;changes=@{status="completed"}}})} | ConvertTo-Json -Depth 8
    Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/works/$($work.id)/action-packages" -Method Post -ContentType "application/json" -Headers @{"Idempotency-Key"="uat-fidelity-$batchSlug-$stamp"} -Body $packageBody | Out-Null
    return $work
}
function Select-SeededWork([string]$WorkId) {
    $workJson = ConvertTo-Json $WorkId -Compress
    $code = @"
async (page) => { await page.reload(); await page.waitForTimeout(500); const select = page.locator('#assistant-work'); if (await select.count()) await select.selectOption($workJson); await page.waitForTimeout(500); }
"@
    Invoke-Cli @("run-code", $code) "select-seeded-work.log" | Out-Null
}

Save-Metadata
try {
    $env:DB_PATH = Join-Path $tempRoot "app.db"; $env:DEFAULT_WORKSPACE_ROOT = Join-Path $tempRoot "workspace"
    $env:CORS_ORIGINS = "http://127.0.0.1:$FrontendPort"; $env:HERMES_DEV_MOCK = "1"; $env:OUTBOX_DISPATCHER_ENABLED = "0"
    Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue
    $env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$BackendPort"; $env:VITE_SHOW_TEST_WORKS = "1"
    $backend = Start-Process -FilePath (Join-Path $repo "backend\.venv\Scripts\python.exe") -ArgumentList @("-m","uvicorn","app.main:app","--host","127.0.0.1","--port","$BackendPort") -WorkingDirectory (Join-Path $repo "backend") -WindowStyle Hidden -RedirectStandardOutput (Join-Path $batchRoot "backend.stdout.log") -RedirectStandardError (Join-Path $batchRoot "backend.stderr.log") -PassThru
    $frontend = Start-Process -FilePath "node.exe" -ArgumentList @((Join-Path $repo "frontend\node_modules\vite\bin\vite.js"),"--host","127.0.0.1","--port","$FrontendPort","--strictPort") -WorkingDirectory (Join-Path $repo "frontend") -WindowStyle Hidden -RedirectStandardOutput (Join-Path $batchRoot "frontend.stdout.log") -RedirectStandardError (Join-Path $batchRoot "frontend.stderr.log") -PassThru
    $metadata.backend_pid=$backend.Id; $metadata.frontend_pid=$frontend.Id; Save-Metadata; Wait-Ready
    Invoke-Cli @("open", "http://127.0.0.1:$FrontendPort") "open.log" | Out-Null
    if ($Batch -eq "AsyncStates") { Capture-Set "empty" @(@{width=390;height=667},@{width=1440;height=900}) }
    $work = Seed-Data; Select-SeededWork $work.id
    switch ($Batch) {
        "AppShell" {
            Capture-Set "app-shell-dark" @(@{width=389;height=667},@{width=390;height=667},@{width=391;height=667},@{width=767;height=1024},@{width=768;height=1024},@{width=769;height=1024},@{width=1023;height=600},@{width=1024;height=600},@{width=1025;height=600},@{width=1440;height=900}) "" "" "appShell"
            Invoke-Cli @("resize","390","667") | Out-Null; Invoke-Cli @("click","button[aria-label='Chuyển sang giao diện sáng']") | Out-Null
            Capture-Set "app-shell-light" @(@{width=390;height=667},@{width=1024;height=600},@{width=1440;height=900}) "" "" "appShell"
            Invoke-Cli @("reload") | Out-Null; Capture-Set "theme-persisted" @(@{width=390;height=667}) "" "" "appShell"
        }
        "PrimarySurfaces" {
            foreach ($surface in @(
                @{id="hermes";selector='button.sidebar-tab:has-text("Hermes")'}, @{id="overview";selector='button.sidebar-tab:has-text("Tổng quan")'},
                @{id="work-overview";selector='button.sidebar-tab:has-text("Công việc")'}, @{id="knowledge";selector='button.sidebar-tab:has-text("Thư viện")'},
                @{id="review";selector='button.sidebar-tab:has-text("Hộp duyệt")'}, @{id="settings";selector='button.sidebar-tab:has-text("Cài đặt")'}
            )) { Capture-Set $surface.id @(@{width=390;height=667},@{width=1024;height=600},@{width=1440;height=900}) $surface.selector }
        }
        "WorkTabs" {
            Capture-Set "work-overview" @(@{width=390;height=667},@{width=1024;height=600},@{width=1440;height=900}) 'button.sidebar-tab:has-text("Công việc")'
            foreach ($tab in @(
                @{id="work-plan";label="Kế hoạch"},@{id="work-conversations";label="Trao đổi"},@{id="work-documents";label="Tài liệu"},
                @{id="work-reports";label="Đầu ra & Báo cáo"},@{id="work-knowledge";label="Tri thức & Bộ nhớ"},@{id="work-capabilities";label="Năng lực"}
            )) { Capture-Set $tab.id @(@{width=390;height=667},@{width=1024;height=600},@{width=1440;height=900}) ('.work-tabs button:has-text("' + $tab.label + '")') }
        }
        "AsyncStates" {
            Capture-Set "populated-approval" @(@{width=390;height=667},@{width=1024;height=600},@{width=1440;height=900}) 'button.sidebar-tab:has-text("Công việc")'
            if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force; $backend.WaitForExit(5000) | Out-Null }
            Invoke-Cli @("reload") | Out-Null; Start-Sleep -Milliseconds 700
            Capture-Set "offline-retry" @(@{width=390;height=667},@{width=1440;height=900}) "" "" "standard" -AllowConsoleErrors
            Add-Capture "offline-network-errors" "expected failure diagnostics" "PASS" "Network console failures are expected only after the isolated backend is stopped."
        }
        "Accessibility" {
            $shot1 = ConvertTo-Json (($batchRoot -replace '\\','/') + '/reduced-motion-keyboard.png') -Compress
            $shot2 = ConvertTo-Json (($batchRoot -replace '\\','/') + '/reflow-400-equivalent.png') -Compress
            $code = @"
async (page) => {
  await page.setViewportSize({width:390,height:667}); await page.emulateMedia({reducedMotion:'reduce',colorScheme:'dark'}); await page.keyboard.press('Tab');
  const focused = await page.evaluate(() => document.activeElement ? (document.activeElement.getAttribute('aria-label') || document.activeElement.textContent || document.activeElement.tagName).trim().slice(0,120) : '');
  if (!focused) throw new Error('Keyboard focus is not visible/addressable'); await page.screenshot({path:$shot1,fullPage:true});
  const trigger = page.locator("button[aria-label='Mở ngữ cảnh công việc']");
  if (await trigger.count() && await trigger.isVisible()) { await trigger.click(); const dialog=page.locator('[role=dialog]').first(); if (!(await dialog.isVisible())) throw new Error('Context drawer did not open'); await page.keyboard.press('Escape'); if (await dialog.isVisible()) throw new Error('Context drawer did not close on Escape'); if (!(await trigger.evaluate(el => el === document.activeElement))) throw new Error('Focus was not restored'); }
  await page.setViewportSize({width:320,height:640}); await page.waitForTimeout(250);
  const overflow=await page.evaluate(() => Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)>innerWidth+1); if (overflow) throw new Error('Reflow-equivalent 400 percent has horizontal overflow');
  await page.screenshot({path:$shot2,fullPage:true}); return JSON.stringify({focused,reducedMotion:true,reflowEquivalent:{width:320,height:640,overflow}});
}
"@
            $codePath = Join-Path $batchRoot "accessibility-code.js"
            $code | Set-Content -Path $codePath -Encoding utf8
            Invoke-Cli @("run-code","--filename",$codePath) "accessibility-metrics.log" | Out-Null
            Add-Capture "reduced-motion-keyboard" "accessibility"; Add-Capture "drawer-focus-escape-restore" "accessibility"; Add-Capture "reflow-400-equivalent" "accessibility"
        }
    }
    $metadata.status="PASS"; $metadata.completed_at=(Get-Date).ToString("o"); Save-Metadata; Write-Output $batchRoot
} catch {
    $metadata.status="FAIL"; $metadata.completed_at=(Get-Date).ToString("o"); $metadata.failures += [ordered]@{message=$_.Exception.Message;recorded_at=(Get-Date).ToString("o")}; Save-Metadata; throw
} finally {
    try { Invoke-Cli @("close") | Out-Null } catch { }
    if ($frontend -and -not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force; $frontend.WaitForExit(5000) | Out-Null }
    if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force; $backend.WaitForExit(5000) | Out-Null }
    foreach ($name in $previousEnv.Keys) { [Environment]::SetEnvironmentVariable($name,$previousEnv[$name],"Process") }
}
