import { describe, expect, it, vi } from 'vitest';
import { createMemoryHubProposal, searchMemoryHub } from './memoryHub';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

describe('Memory Hub operator API', () => {
  it('never sends an Authorization header from the browser', async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => [] });
    await searchMemoryHub({ project_id: 'project-a' });
    await createMemoryHubProposal({ kind: 'preference', memory_key: 'language', content: 'Vietnamese' });

    for (const [, options] of fetchMock.mock.calls) {
      expect(options.headers).not.toHaveProperty('Authorization');
    }
  });
});
