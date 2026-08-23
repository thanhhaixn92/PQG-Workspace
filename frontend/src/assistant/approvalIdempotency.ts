export interface ApprovalIdentity {
  packageId: string;
  expectedRevision: number;
  expectedPayloadHash: string;
}

export type IdempotencyKeyFactory = () => string;

export const approvalIdentityKey = ({
  packageId,
  expectedRevision,
  expectedPayloadHash,
}: ApprovalIdentity): string => JSON.stringify([packageId, expectedRevision, expectedPayloadHash]);

/**
 * Keeps one idempotency key for each logical approval during the current UI session.
 * A repeat click or retry after a transport error uses the same key. A different
 * package revision or payload hash produces a different logical identity and key.
 */
export const createApprovalIdempotencyRegistry = (createKey: IdempotencyKeyFactory) => {
  const keys = new Map<string, string>();

  return {
    get(identity: ApprovalIdentity): string {
      const key = approvalIdentityKey(identity);
      const existing = keys.get(key);
      if (existing) return existing;

      const created = createKey();
      keys.set(key, created);
      return created;
    },
  };
};
