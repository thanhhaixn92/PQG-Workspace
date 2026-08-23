# V2.2 Fidelity Ledger

Gate status: `PARTIAL`. Năm batch cô lập cuối đều PASS cho phạm vi đã chạy; browser zoom 200% thật đã PASS bằng Chrome native, nhưng full cross-product screen × state × viewport vẫn chưa hoàn tất, nên không nâng claim.

Latest technical run on 2026-08-15 used isolated services and `uat-codex-` data. Evidence root: `output/playwright/v22-batched-20260815-075743/`. Five final PASS batches contain 62 screenshots. The earlier `primarysurfaces-20260815-075842` FAIL exposed the Review/Memory Hub same-origin 403 and `worktabs-20260815-075842` was interrupted when its parallel sibling failed; both are retained as superseded evidence and are not counted. The corrected reruns passed.

Actual browser zoom evidence: `output/playwright/v22-brandzoom-20260815-0900/`. Chrome 151 was launched with an isolated profile against frontend `:8872` and backend `:8871`, using temporary SQLite/workspace paths prefixed `uat-codex-`. Native `Ctrl+=` steps reached Chrome toolbar `Zoom: 200%`; the isolated profile stored host zoom level `3.8017840169239308`, equivalent to exactly 200%. `chrome-actual-zoom-200.png` and `browser-zoom-200-log.json` record the browser frame, title, product label, temporary Work and responsive bottom navigation. No CSS zoom, device emulation or real user data was used. Outer Chrome window was 945×1030; the CSS viewport was not independently recorded, so no exact viewport row below is inferred from this run.

| Final batch | Covered evidence | Result |
|---|---|---|
| `appshell-20260815-075743` | 10 breakpoint edges dark; light at 390/1024/1440; theme persistence | PASS |
| `primarysurfaces-20260815-080325` | Hermes, Overview, Work, Knowledge, Review, Settings at 390/1024/1440; console/overflow assertions | PASS |
| `worktabs-20260815-080436` | Overview, Plan, Conversations, Documents, Reports, Knowledge/Memory, Capabilities at 390/1024/1440 | PASS |
| `asyncstates-20260815-080549` | empty 390/1440; populated/approval 390/1024/1440; offline/retry 390/1440 | PASS |
| `accessibility-20260815-080638` | reduced motion, keyboard focus, drawer Escape/focus restore, 320px reflow equivalent to 400% | PASS |
| `v22-brandzoom-20260815-0900` | actual Chrome zoom 200%, DIRAP Local Workbench title/App Shell, temporary Work, bottom navigation/composer | PASS |

## Evidence convention

- Use isolated `uat-codex-` data; never use the real database/workspace.
- Save screenshots/logs under an explicitly named evidence directory and record relative paths here.
- Record `PASS`, `FAIL`, or `NOT RUN`; never leave a blank cell or infer a theme/zoom state from another run.
- For every run record browser/version, frontend/backend commit or diff identity, timestamp, console errors, horizontal overflow and clipping.

## Viewport matrix

| Viewport | Navigation expectation | Empty | Populated | Partial/offline/retry | Approval/long content | Dark | Light | Keyboard/focus | Reduced motion | Zoom 200% | Reflow 400% | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 389×667 | bottom nav | NOT RUN | PASS | NOT RUN | NOT RUN | PASS | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | `appshell-*/app-shell-dark-389x667.png` | PARTIAL |
| 390×667 | bottom nav | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | NOT RUN | PASS | final five batches | PARTIAL |
| 391×667 | bottom nav | NOT RUN | PASS | NOT RUN | NOT RUN | PASS | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | `appshell-*/app-shell-dark-391x667.png` | PARTIAL |
| 767×1024 | bottom nav | NOT RUN | PASS | NOT RUN | NOT RUN | PASS | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | `appshell-*/app-shell-dark-767x1024.png` | PARTIAL |
| 768×1024 | bottom nav | NOT RUN | PASS | NOT RUN | NOT RUN | PASS | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | `appshell-*/app-shell-dark-768x1024.png` | PARTIAL |
| 769×1024 | 72px rail | NOT RUN | PASS | NOT RUN | NOT RUN | PASS | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | `appshell-*/app-shell-dark-769x1024.png` | PARTIAL |
| 1023×600 | 72px rail/overlay drawer | NOT RUN | PASS | NOT RUN | NOT RUN | PASS | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | `appshell-*/app-shell-dark-1023x600.png` | PARTIAL |
| 1024×600 | 72px rail/overlay drawer | NOT RUN | PASS | NOT RUN | PASS | PASS | PASS | NOT RUN | NOT RUN | NOT RUN | NOT RUN | primary/Work/async/AppShell batches | PARTIAL |
| 1025×600 | desktop navigation | NOT RUN | PASS | NOT RUN | NOT RUN | PASS | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | `appshell-*/app-shell-dark-1025x600.png` | PARTIAL |
| 1440×900 | desktop navigation | PASS | PASS | PASS | PASS | PASS | PASS | NOT RUN | NOT RUN | NOT RUN | NOT RUN | primary/Work/async/AppShell batches | PARTIAL |

## Per-screen checklist

Apply the matrix to Hermes, Overview, Work list/dashboard/plan/conversations/documents/reports/capabilities, Knowledge, Review and Settings. Confirm composer/primary action remains visible at 390px; modal/drawer has backdrop, Escape, focus trap/restore and body scroll lock; no secret/raw system path appears; console has no error; theme toggle works without an active Work and persists after reload.

Final verdict: `PARTIAL`. Breakpoint/navigation, representative screen/tab coverage, async/offline, theme, reduced motion, keyboard/focus, reflow và browser zoom 200% thật đã có evidence. Full screen×state×viewport cross-product vẫn chưa hoàn tất; các ô `NOT RUN` trong bảng không được suy diễn từ lượt zoom. Human usability đã được người dùng hoãn hậu v2.2 và vẫn `NOT RUN`.
