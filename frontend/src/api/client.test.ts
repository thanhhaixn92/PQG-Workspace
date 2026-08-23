import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { apiFetch, ApiError, BASE_URL } from './client';

describe('apiFetch', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('should parse JSON on 200 OK', async () => {
    const mockData = { id: 1, name: 'Test' };
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await apiFetch('/test');
    expect(result).toEqual(mockData);
    expect(global.fetch).toHaveBeenCalledWith(`${BASE_URL}/test`, expect.any(Object));
  });

  it('should return undefined on 204 No Content', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: async () => { throw new Error('Should not be called'); },
    });

    const result = await apiFetch('/test-204');
    expect(result).toBeUndefined();
    expect(global.fetch).toHaveBeenCalledWith(`${BASE_URL}/test-204`, expect.any(Object));
  });

  it('should throw ApiError on non-2xx response', async () => {
    (global.fetch as any).mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      text: async () => 'Resource not found',
    });

    await expect(apiFetch('/test-404')).rejects.toThrow(ApiError);
    await expect(apiFetch('/test-404')).rejects.toThrow('Resource not found');
  });

  it('keeps the JSON content type when an idempotency header is supplied', async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ ok: true }) });

    await apiFetch('/report', { method: 'POST', headers: { 'Idempotency-Key': 'report-key' }, body: JSON.stringify({ title: 'Báo cáo' }) });

    expect(global.fetch).toHaveBeenCalledWith(`${BASE_URL}/report`, expect.objectContaining({
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': 'report-key' },
    }));
  });
});
