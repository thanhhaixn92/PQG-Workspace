import { test, expect } from '@playwright/test';

const BACKEND_URL = 'http://127.0.0.1:8000';
const FRONTEND_URL = 'http://127.0.0.1:5173';

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

// Thread ID storage
const threadIds: Record<string, string> = {};

test.describe.configure({ retries: 0 });

test.describe('Gate 2 Package A: Canonical Resolver UAT (API Mode)', () => {

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

  // Helper: resolve canonical thread via API
  async function resolveThread(request: any, workId: string, conversationId: string) {
    const response = await request.post(
      `${BACKEND_URL}/api/assistant/works/${workId}/conversations/${conversationId}/assistant-thread`
    );
    expect(response.status()).toBe(200);
    return await response.json();
  }

  // Helper: create a turn via API
  async function createTurn(request: any, threadId: string, prompt: string, workId: string, conversationId: string) {
    const response = await request.post(
      `${BACKEND_URL}/api/assistant/threads/${threadId}/turns`,
      {
        data: { prompt, work_id: workId, conversation_id: conversationId }
      }
    );
    expect(response.status()).toBe(200);
    return await response.json();
  }

  test('Preflight: Backend health', async ({ request }) => {
    const healthResponse = await request.get(`${BACKEND_URL}/health`);
    expect(healthResponse.status()).toBe(200);
    const health = await healthResponse.json();
    expect(health.status).toBe('ok');
  });

  // ========== WORK A - CONVERSATION A1 ==========

  test('Work A / A1: Canonical resolver returns thread', async ({ request }) => {
    const thread = await resolveThread(request, workAId, convA1Id);
    expect(thread.work_id).toBe(workAId);
    expect(thread.conversation_id).toBe(convA1Id);
    expect(thread.id).toBeTruthy();
    threadIds['A1'] = thread.id;
  });

  test('Work A / A1: Resolver is idempotent', async ({ request }) => {
    const [thread1, thread2] = await Promise.all([
      resolveThread(request, workAId, convA1Id),
      resolveThread(request, workAId, convA1Id),
    ]);
    expect(thread1.id).toBe(thread2.id);
    expect(thread1.id).toBe(threadIds['A1']);
  });

  test('Work A / A1: Create turn with resolved thread', async ({ request }) => {
    const turns = await createTurn(request, threadIds['A1'], 'Xin chào A1', workAId, convA1Id);
    expect(turns.length).toBe(2); // user + assistant
    expect(turns[0].role).toBe('user');
    expect(turns[1].role).toBe('assistant');
    expect(turns[1].work_id).toBe(workAId);
    expect(turns[1].conversation_id).toBe(convA1Id);
  });

  // ========== WORK A - CONVERSATION A2 ==========

  test('Work A / A2: Canonical resolver returns DIFFERENT thread', async ({ request }) => {
    const thread = await resolveThread(request, workAId, convA2Id);
    expect(thread.work_id).toBe(workAId);
    expect(thread.conversation_id).toBe(convA2Id);
    expect(thread.id).not.toBe(threadIds['A1']);
    threadIds['A2'] = thread.id;
  });

  test('Work A / A2: Resolver is idempotent', async ({ request }) => {
    const [thread1, thread2] = await Promise.all([
      resolveThread(request, workAId, convA2Id),
      resolveThread(request, workAId, convA2Id),
    ]);
    expect(thread1.id).toBe(thread2.id);
    expect(thread1.id).toBe(threadIds['A2']);
  });

  test('Work A / A2: Create turn with resolved thread', async ({ request }) => {
    const turns = await createTurn(request, threadIds['A2'], 'Xin chào A2', workAId, convA2Id);
    expect(turns.length).toBe(2);
    expect(turns[1].work_id).toBe(workAId);
    expect(turns[1].conversation_id).toBe(convA2Id);
  });

  // ========== WORK B - CONVERSATION B1 ==========

  test('Work B / B1: Canonical resolver returns thread', async ({ request }) => {
    const thread = await resolveThread(request, workBId, convB1Id);
    expect(thread.work_id).toBe(workBId);
    expect(thread.conversation_id).toBe(convB1Id);
    expect(thread.id).not.toBe(threadIds['A1']);
    expect(thread.id).not.toBe(threadIds['A2']);
    threadIds['B1'] = thread.id;
  });

  test('Work B / B1: Resolver is idempotent', async ({ request }) => {
    const [thread1, thread2] = await Promise.all([
      resolveThread(request, workBId, convB1Id),
      resolveThread(request, workBId, convB1Id),
    ]);
    expect(thread1.id).toBe(thread2.id);
    expect(thread1.id).toBe(threadIds['B1']);
  });

  test('Work B / B1: Create turn with resolved thread', async ({ request }) => {
    const turns = await createTurn(request, threadIds['B1'], 'Xin chào B1', workBId, convB1Id);
    expect(turns.length).toBe(2);
    expect(turns[1].work_id).toBe(workBId);
    expect(turns[1].conversation_id).toBe(convB1Id);
  });

  // ========== WORK B - CONVERSATION B2 ==========

  test('Work B / B2: Canonical resolver returns DIFFERENT thread', async ({ request }) => {
    const thread = await resolveThread(request, workBId, convB2Id);
    expect(thread.work_id).toBe(workBId);
    expect(thread.conversation_id).toBe(convB2Id);
    expect(thread.id).not.toBe(threadIds['B1']);
    threadIds['B2'] = thread.id;
  });

  test('Work B / B2: Resolver is idempotent', async ({ request }) => {
    const [thread1, thread2] = await Promise.all([
      resolveThread(request, workBId, convB2Id),
      resolveThread(request, workBId, convB2Id),
    ]);
    expect(thread1.id).toBe(thread2.id);
    expect(thread1.id).toBe(threadIds['B2']);
  });

  test('Work B / B2: Create turn with resolved thread', async ({ request }) => {
    const turns = await createTurn(request, threadIds['B2'], 'Xin chào B2', workBId, convB2Id);
    expect(turns.length).toBe(2);
    expect(turns[1].work_id).toBe(workBId);
    expect(turns[1].conversation_id).toBe(convB2Id);
  });

  // ========== GLOBAL THREAD REJECTION ==========

  test('Global thread cannot create Work-scoped turn', async ({ request }) => {
    // Create global thread
    const globalThreadResponse = await request.post(`${BACKEND_URL}/api/assistant/threads`, {
      data: { title: 'Global Test' }
    });
    expect(globalThreadResponse.status()).toBe(201);
    const globalThread = await globalThreadResponse.json();
    expect(globalThread.work_id).toBeNull();
    expect(globalThread.conversation_id).toBeNull();

    // Try to create turn with work_id - should fail
    const turnResponse = await request.post(
      `${BACKEND_URL}/api/assistant/threads/${globalThread.id}/turns`,
      {
        data: { prompt: 'Should fail', work_id: workAId, conversation_id: convA1Id }
      }
    );
    expect([409, 422]).toContain(turnResponse.status());
  });

  test('Legacy Work-only thread creation rejected', async ({ request }) => {
    const legacyThreadResponse = await request.post(`${BACKEND_URL}/api/assistant/threads`, {
      data: { title: 'Legacy Work Thread', work_id: workAId }
    });
    expect(legacyThreadResponse.status()).toBe(422);
  });

  // ========== FINAL VERIFICATION ==========

  test('Final: Four distinct thread IDs verified', async () => {
    const allThreadIds = [
      threadIds['A1'],
      threadIds['A2'],
      threadIds['B1'],
      threadIds['B2']
    ];

    const uniqueThreads = new Set(allThreadIds);
    expect(uniqueThreads.size).toBe(4);

    console.log('=== THREAD ID SUMMARY ===');
    Object.entries(threadIds).forEach(([key, value]) => {
      console.log(`${key}: ${value}`);
    });
  });
});