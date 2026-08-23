import { describe, expect, it, vi } from 'vitest';
import { createApprovalIdempotencyRegistry } from './approvalIdempotency';

describe('approval idempotency registry', () => {
  it('reuses one key for double-click and transport retry of the same logical approval', () => {
    const createKey = vi.fn()
      .mockReturnValueOnce('key-1')
      .mockReturnValueOnce('key-2');
    const registry = createApprovalIdempotencyRegistry(createKey);
    const approval = {
      packageId: 'package-1',
      expectedRevision: 3,
      expectedPayloadHash: 'canonical-hash-v3',
    };

    const firstClick = registry.get(approval);
    const retryAfterNetworkFailure = registry.get(approval);

    expect(firstClick).toBe('key-1');
    expect(retryAfterNetworkFailure).toBe('key-1');
    expect(createKey).toHaveBeenCalledTimes(1);
  });

  it('creates a new key when revision or canonical payload hash changes', () => {
    const createKey = vi.fn()
      .mockReturnValueOnce('key-v3')
      .mockReturnValueOnce('key-v4')
      .mockReturnValueOnce('key-new-hash');
    const registry = createApprovalIdempotencyRegistry(createKey);

    expect(registry.get({ packageId: 'package-1', expectedRevision: 3, expectedPayloadHash: 'hash-v3' })).toBe('key-v3');
    expect(registry.get({ packageId: 'package-1', expectedRevision: 4, expectedPayloadHash: 'hash-v4' })).toBe('key-v4');
    expect(registry.get({ packageId: 'package-1', expectedRevision: 4, expectedPayloadHash: 'hash-v4-recomputed' })).toBe('key-new-hash');
    expect(createKey).toHaveBeenCalledTimes(3);
  });
});
