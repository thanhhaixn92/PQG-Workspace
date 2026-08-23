import { test, expect, type Page } from '@playwright/test';
import { join } from 'path';

const BACKEND_URL = 'http://127.0.0.1:8000';
const FRONTEND_URL = 'http://127.0.0.1:5173';
const ARTIFACTS_DIR = join(__dirname, 'artifacts');

// Test data
const WORK_A_TITLE = 'Công việc A — UAT Resolver';
const WORK_B_TITLE = 'Công việc B — UAT Resolver';
const CONV_A1_TITLE = 'Phiên A1 — Trao đổi đầu tiên';
const CONV_A2_TITLE = 'Phiên A2 — Trao đổi thứ hai';
const CONV_B1_TITLE = 'Phiên B1 — Trao đổi đầu tiên';
const CONV_B2_TITLE = 'Phiên B2 — Trao đổi thứ hai';

let workAId: string;
let workBId: string;
let convA1Id: string;
let convA2Id: string;
let convB1Id: string;
let convB2Id: string;

// Test data storage
const threadIds: Record<string, string> = {};

test.describe.configure({ retries: 0 });

test.describe('Gate 2 Package A: Canonical Resolver UAT', () => {

  test.beforeAll(async ({ request }) => {
    // Create Work A
    const workAResponse = await request.post(`${BACKEND_URL}/api/sessions`, {
      data: { title: WORK_A_TITLE, goal: 'Kiểm tra resolver canonical cho Work A', data_scope: 'work_only' }
    });
    expect(workAResponse.status()).toBe(201);
    workAId = (await workAResponse.json()).id;

    // Create Work B
    const workBResponse = await request.post(`${BACKEND_URL}/api/sessions`, {
      data: { title: WORK_B_TITLE, goal: 'Kiểm tra resolver canonical cho Work B', data_scope: 'work_only' }
    });
    expect(workBResponse.status()).toBe(201);
    workBId = (await workBResponse.json()).id;

    // Create Conversations for Work A
    const convA1Response = await request.post(`${BACKEND_URL}/api/works/${workAId}/conversations`, {
      data: { title: CONV_A1_TITLE, purpose: 'GYO Panel + WorkHub cùng thread' }
    });
    expect(convA1Response.status()).toBe(201);
    convA1Id = (await convA1Response.json()).id;

    const convA2Response = await request.post(`${BACKEND_URL}/api/works/${workAId}/conversations`, {
      data: { title: CONV_A2_TITLE, purpose: 'Thread khác biệt với A1' }
    });
    expect(convA2Response.status()).toBe(201);
    convA2Id = (await convA2Response.json()).id;

    // Create Conversations for Work B
    const convB1Response = await request.post(`${BACKEND_URL}/api/works/${workBId}/conversations`, {
      data: { title: CONV_B1_TITLE, purpose: 'GYO Panel + WorkHub cùng thread' }
    });
    expect(convB1Response.status()).toBe(201);
    convB1Id = (await convB1Response.json()).id;

    const convB2Response = await request.post(`${BACKEND_URL}/api/works/${workBId}/conversations`, {
      data: { title: CONV_B2_TITLE, purpose: 'Thread khác biệt với B1' }
    });
    expect(convB2Response.status()).toBe(201);
    convB2Id = (await convB2Response.json()).id;
  });

  // Helper: navigate to frontend and wait for load
  async function gotoFrontend(page: Page) {
    await page.goto(FRONTEND_URL, { waitUntil: 'networkidle', timeout: 30000 });
    // Wait for any of these indicators that the app has loaded
    await Promise.race([
      page.waitForSelector('.work-hub', { timeout: 15000 }).catch(() => null),
      page.waitForSelector('h1:has-text("Công việc")', { timeout: 15000 }).catch(() => null),
      page.waitForSelector('text=Công việc', { timeout: 15000 }).catch(() => null),
      page.waitForSelector('[data-testid="work-hub"]', { timeout: 15000 }).catch(() => null),
    ]);
  }

  // Helper: select a Work in the sidebar/selector
  async function selectWork(page: Page, workTitle: string) {
    // Use the select#assistant-work which is the main Work selector in GYO Panel
    const workSelect = page.locator('select#assistant-work').first();
    if (await workSelect.count()) {
      // Wait for options to be populated - check for the specific work title in options
      await page.waitForFunction(
        (title) => {
          const select = document.querySelector('select#assistant-work');
          if (!select) return false;
          return Array.from(select.options).some(opt => opt.text.includes(title));
        },
        workTitle,
        { timeout: 15000 }
      );
      await workSelect.selectOption({ label: workTitle });
      await page.waitForTimeout(500);
    } else {
      // Fallback: click Work in sidebar if visible
      const workItem = page.locator('.session-list-item, .work-item, [data-work-id]').filter({ hasText: workTitle }).first();
      if (await workItem.count()) {
        await workItem.click();
        await page.waitForTimeout(500);
      }
    }
  }

  // Helper: select a Conversation in GYO Panel
  async function selectConversationInGyo(page: Page, conversationTitle: string) {
    const convSelect = page.locator('select[aria-label="Phiên Công việc"]').first();
    if (await convSelect.count()) {
      await page.waitForFunction(
        (title) => {
          const select = document.querySelector('select[aria-label="Phiên Công việc"]');
          if (!select) return false;
          return Array.from(select.options).some(opt => opt.text.includes(title));
        },
        conversationTitle,
        { timeout: 15000 }
      );
      await convSelect.selectOption({ label: conversationTitle });
      await page.waitForTimeout(500);
    }
  }

  // Helper: select a Conversation in WorkHub
  async function selectConversationInWorkHub(page: Page, conversationTitle: string) {
    const convButton = page.locator('.conversation-list-item, button:has-text("' + conversationTitle + '")').first();
    if (await convButton.count()) {
      await convButton.click();
      await page.waitForTimeout(500);
    }
  }

  // Helper: send a prompt in GYO Panel
  async function sendPromptInGyo(page: Page, prompt: string) {
    const textarea = page.locator('textarea[placeholder*="GYO"], textarea[placeholder*="trợ lý"], .assistant-chat textarea').first();
    await textarea.fill(prompt);
    const sendButton = page.locator('button:has-text("Gửi"), button:has(svg.lucide-send)').first();
    await sendButton.click();

    // Wait for response to complete (stream done)
    await page.waitForSelector('.assistant-live-response, .conversation-message.assistant:not(.running)', { timeout: 30000 });
    await page.waitForTimeout(1000);
  }

  // Helper: send a prompt in WorkHub ConversationWorkspace
  async function sendPromptInWorkHub(page: Page, prompt: string) {
    const textarea = page.locator('.conversation-composer textarea, .conversation-workspace textarea').first();
    await textarea.fill(prompt);
    const sendButton = page.locator('.conversation-composer button:has-text("Gửi"), .conversation-workspace button:has-text("Gửi")').first();
    await sendButton.click();

    // Wait for response
    await page.waitForSelector('.conversation-message.assistant:not(.running)', { timeout: 30000 });
    await page.waitForTimeout(1000);
  }

  // Helper: get thread ID from GYO Panel (from data attribute or DOM)
  async function getGyoThreadId(page: Page): Promise<string | null> {
    // Try to get from data attribute
    const threadElement = page.locator('[data-thread-id], .assistant-thread-bar').first();
    if (await threadElement.count()) {
      const id = await threadElement.getAttribute('data-thread-id');
      if (id) return id;
    }
    // Try from conversation info in DOM
    const scriptContent = await page.evaluate(() => {
      const scripts = Array.from(document.querySelectorAll('script'));
      for (const s of scripts) {
        if (s.textContent?.includes('threadId') || s.textContent?.includes('thread_id')) {
          const match = s.textContent.match(/thread[=\"_]?id[\"\\s:=]+[\"']([a-f0-9-]{36})/i);
          if (match) return match[1];
        }
      }
      return null;
    });
    return scriptContent;
  }

  // Helper: get thread ID from WorkHub ConversationWorkspace
  async function getWorkHubThreadId(page: Page): Promise<string | null> {
    // Check if there's a thread ID in the DOM
    const scriptContent = await page.evaluate(() => {
      const scripts = Array.from(document.querySelectorAll('script'));
      for (const s of scripts) {
        if (s.textContent?.includes('threadId') || s.textContent?.includes('thread_id')) {
          const match = s.textContent.match(/thread[=\"_]?id[\"\\s:=]+[\"']([a-f0-9-]{36})/i);
          if (match) return match[1];
        }
      }
      return null;
    });
    return scriptContent;
  }

  // Helper: take screenshot
  async function takeScreenshot(page: Page, name: string) {
    const path = join(ARTIFACTS_DIR, 'screenshots', `${name}.png`);
    await page.screenshot({ path, fullPage: true });
    return path;
  }

  // Setup console log capture
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      (window as any).__CONSOLE_LOGS__ = [];
      const originalLog = console.log;
      const originalError = console.error;
      const originalWarn = console.warn;
      console.log = (...args) => { (window as any).__CONSOLE_LOGS__.push('[LOG] ' + args.join(' ')); originalLog.apply(console, args); };
      console.error = (...args) => { (window as any).__CONSOLE_LOGS__.push('[ERROR] ' + args.join(' ')); originalError.apply(console, args); };
      console.warn = (...args) => { (window as any).__CONSOLE_LOGS__.push('[WARN] ' + args.join(' ')); originalWarn.apply(console, args); };
    });
  });

  test('Preflight: Backend health and Frontend load', async ({ page }) => {
    // Backend health
    const healthResponse = await page.request.get(`${BACKEND_URL}/health`);
    expect(healthResponse.status()).toBe(200);
    const health = await healthResponse.json();
    expect(health.status).toBe('ok');

    // Frontend load
    await gotoFrontend(page);
    await takeScreenshot(page, '00-preflight-loaded');
  });

  // ========== WORK A - CONVERSATION A1 ==========

  test('Work A / A1: GYO Panel resolves thread', async ({ page }) => {
    await gotoFrontend(page);
    await selectWork(page, WORK_A_TITLE);
    await selectConversationInGyo(page, CONV_A1_TITLE);
    await sendPromptInGyo(page, 'Xin chào, đây là test A1');

    const threadId = await getGyoThreadId(page);
    expect(threadId).not.toBeNull();
    threadIds['A1-GYO'] = threadId!;

    await takeScreenshot(page, '01-gyo-a1-thread');
  });

  test('Work A / A1: WorkHub shares SAME thread', async ({ page }) => {
    await gotoFrontend(page);
    await selectWork(page, WORK_A_TITLE);
    // Navigate to Conversations tab
    await page.click('button:has-text("Trao đổi"), [role="tab"]:has-text("Trao đổi")').catch(() => {});
    await page.waitForTimeout(500);
    await selectConversationInWorkHub(page, CONV_A1_TITLE);
    await sendPromptInWorkHub(page, 'Test từ WorkHub A1');

    const threadId = await getWorkHubThreadId(page);
    expect(threadId).not.toBeNull();
    threadIds['A1-WorkHub'] = threadId!;

    // Verify same thread
    expect(threadIds['A1-WorkHub']).toBe(threadIds['A1-GYO']);

    await takeScreenshot(page, '02-workhub-a1-same-thread');
  });

  // ========== WORK A - CONVERSATION A2 ==========

  test('Work A / A2: GYO Panel resolves DIFFERENT thread', async ({ page }) => {
    await gotoFrontend(page);
    await selectWork(page, WORK_A_TITLE);
    await selectConversationInGyo(page, CONV_A2_TITLE);
    await sendPromptInGyo(page, 'Xin chào, đây là test A2');

    const threadId = await getGyoThreadId(page);
    expect(threadId).not.toBeNull();
    threadIds['A2-GYO'] = threadId!;

    // Verify different from A1
    expect(threadIds['A2-GYO']).not.toBe(threadIds['A1-GYO']);

    await takeScreenshot(page, '03-gyo-a2-different-thread');
  });

  test('Work A / A2: WorkHub shares SAME thread', async ({ page }) => {
    await gotoFrontend(page);
    await selectWork(page, WORK_A_TITLE);
    await page.click('button:has-text("Trao đổi"), [role="tab"]:has-text("Trao đổi")').catch(() => {});
    await page.waitForTimeout(500);
    await selectConversationInWorkHub(page, CONV_A2_TITLE);
    await sendPromptInWorkHub(page, 'Test từ WorkHub A2');

    const threadId = await getWorkHubThreadId(page);
    expect(threadId).not.toBeNull();
    threadIds['A2-WorkHub'] = threadId!;

    // Verify same thread
    expect(threadIds['A2-WorkHub']).toBe(threadIds['A2-GYO']);

    await takeScreenshot(page, '04-workhub-a2-same-thread');
  });

  // ========== WORK B - CONVERSATION B1 ==========

  test('Work B / B1: GYO Panel resolves thread', async ({ page }) => {
    await gotoFrontend(page);
    await selectWork(page, WORK_B_TITLE);
    await selectConversationInGyo(page, CONV_B1_TITLE);
    await sendPromptInGyo(page, 'Xin chào, đây là test B1');

    const threadId = await getGyoThreadId(page);
    expect(threadId).not.toBeNull();
    threadIds['B1-GYO'] = threadId!;

    // Verify different from Work A threads
    expect(threadIds['B1-GYO']).not.toBe(threadIds['A1-GYO']);
    expect(threadIds['B1-GYO']).not.toBe(threadIds['A2-GYO']);

    await takeScreenshot(page, '05-gyo-b1-thread');
  });

  test('Work B / B1: WorkHub shares SAME thread', async ({ page }) => {
    await gotoFrontend(page);
    await selectWork(page, WORK_B_TITLE);
    await page.click('button:has-text("Trao đổi"), [role="tab"]:has-text("Trao đổi")').catch(() => {});
    await page.waitForTimeout(500);
    await selectConversationInWorkHub(page, CONV_B1_TITLE);
    await sendPromptInWorkHub(page, 'Test từ WorkHub B1');

    const threadId = await getWorkHubThreadId(page);
    expect(threadId).not.toBeNull();
    threadIds['B1-WorkHub'] = threadId!;

    // Verify same thread
    expect(threadIds['B1-WorkHub']).toBe(threadIds['B1-GYO']);

    await takeScreenshot(page, '06-workhub-b1-same-thread');
  });

  // ========== WORK B - CONVERSATION B2 ==========

  test('Work B / B2: GYO Panel resolves DIFFERENT thread', async ({ page }) => {
    await gotoFrontend(page);
    await selectWork(page, WORK_B_TITLE);
    await selectConversationInGyo(page, CONV_B2_TITLE);
    await sendPromptInGyo(page, 'Xin chào, đây là test B2');

    const threadId = await getGyoThreadId(page);
    expect(threadId).not.toBeNull();
    threadIds['B2-GYO'] = threadId!;

    // Verify different from B1
    expect(threadIds['B2-GYO']).not.toBe(threadIds['B1-GYO']);

    await takeScreenshot(page, '07-gyo-b2-different-thread');
  });

  test('Work B / B2: WorkHub shares SAME thread', async ({ page }) => {
    await gotoFrontend(page);
    await selectWork(page, WORK_B_TITLE);
    await page.click('button:has-text("Trao đổi"), [role="tab"]:has-text("Trao đổi")').catch(() => {});
    await page.waitForTimeout(500);
    await selectConversationInWorkHub(page, CONV_B2_TITLE);
    await sendPromptInWorkHub(page, 'Test từ WorkHub B2');

    const threadId = await getWorkHubThreadId(page);
    expect(threadId).not.toBeNull();
    threadIds['B2-WorkHub'] = threadId!;

    // Verify same thread
    expect(threadIds['B2-WorkHub']).toBe(threadIds['B2-GYO']);

    await takeScreenshot(page, '08-workhub-b2-same-thread');
  });

  // ========== STATE ISOLATION CHECKS ==========

  test('Switch Conversation in Work A clears state', async ({ page }) => {
    await gotoFrontend(page);
    await selectWork(page, WORK_A_TITLE);

    // Start with A1
    await selectConversationInGyo(page, CONV_A1_TITLE);
    await sendPromptInGyo(page, 'Test state clear A1');
    const threadA1 = await getGyoThreadId(page);

    // Switch to A2
    await selectConversationInGyo(page, CONV_A2_TITLE);

    // Verify thread ID changed (new conversation = new thread)
    const threadA2 = await getGyoThreadId(page);
    expect(threadA2).not.toBe(threadA1);

    // Verify can send a new message
    await sendPromptInGyo(page, 'Test state clear A2 after switch');
    const threadAfter = await getGyoThreadId(page);
    expect(threadAfter).toBe(threadA2);
  });

  test('Switch Work A -> Work B clears ALL state', async ({ page }) => {
    await gotoFrontend(page);

    // Start with Work A
    await selectWork(page, WORK_A_TITLE);
    await selectConversationInGyo(page, CONV_A1_TITLE);
    await sendPromptInGyo(page, 'Test Work A state');
    const threadWorkA = await getGyoThreadId(page);

    // Switch to Work B
    await selectWork(page, WORK_B_TITLE);
    await selectConversationInGyo(page, CONV_B1_TITLE);

    // Verify fresh state - new thread
    const threadWorkB = await getGyoThreadId(page);
    expect(threadWorkB).not.toBe(threadWorkA);

    // Verify can send message in Work B
    await sendPromptInGyo(page, 'Test Work B after switch');
    const threadAfter = await getGyoThreadId(page);
    expect(threadAfter).toBe(threadWorkB);
  });

  // ========== FINAL VERIFICATION ==========

  test('Final: Four distinct thread IDs verified', async ({ page }) => {
    // Verify all 4 conversations have distinct thread IDs
    const allThreadIds = [
      threadIds['A1-GYO'],
      threadIds['A2-GYO'],
      threadIds['B1-GYO'],
      threadIds['B2-GYO']
    ];

    const uniqueThreads = new Set(allThreadIds);
    expect(uniqueThreads.size).toBe(4);

    // Also verify WorkHub threads match GYO threads
    expect(threadIds['A1-WorkHub']).toBe(threadIds['A1-GYO']);
    expect(threadIds['A2-WorkHub']).toBe(threadIds['A2-GYO']);
    expect(threadIds['B1-WorkHub']).toBe(threadIds['B1-GYO']);
    expect(threadIds['B2-WorkHub']).toBe(threadIds['B2-GYO']);

    // Log for report
    console.log('=== THREAD ID SUMMARY ===');
    Object.entries(threadIds).forEach(([key, value]) => {
      console.log(`${key}: ${value}`);
    });

    await takeScreenshot(page, '09-final-four-distinct-threads');
  });
});

// Cleanup artifacts after all tests
test.afterAll(async () => {
  // Artifacts are kept for review
  console.log(`Artifacts saved to: ${ARTIFACTS_DIR}`);
});