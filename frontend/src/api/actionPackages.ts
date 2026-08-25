export interface ActionStep { id: string; sort_order: number; kind: string; risk_level: string; status: string; input: Record<string, unknown>; output?: Record<string, unknown> | null; error?: string | null; capability?: string | null; expected_version?: Record<string, unknown> | null; postcondition?: Record<string, unknown> | null }
export interface ActionPackage {
  id: string; session_id: string; conversation_id?: string | null; title: string; description?: string | null;
  package_hash: string; payload_hash?: string | null; approved_payload_hash?: string | null; status: string;
  revision?: number | null; approved_revision?: number | null; expires_at?: number | null; approval_ttl_seconds?: number | null;
  created_at: number; updated_at: number; steps: ActionStep[]; capabilities?: string[];
  snapshot?: Record<string, unknown>; preconditions?: Array<Record<string, unknown>>;
  budget?: Record<string, unknown>; resolved_payload?: Record<string, unknown>;
}
export interface ActionPackageProposal { title: string; description?: string | null; conversation_id?: string | null; source_proposal_part_id?: string | null; artifact_ids?: string[]; steps: Array<{ kind: 'work_plan_step_update' | 'work_status_update'; input: Record<string, unknown> }> }
import { apiFetch } from './client';

export const getWorkActionPackages = (workId: string) => apiFetch<ActionPackage[]>(`/api/works/${encodeURIComponent(workId)}/action-packages`);
export const getActionPackage = (packageId: string) => apiFetch<ActionPackage>(`/api/action-packages/${encodeURIComponent(packageId)}`);
export interface ActionPackagePreflight {
  package_id?: string | null;
  revision?: number | null;
  payload_hash?: string | null;
  valid: boolean;
  errors?: string[];
  snapshot?: Record<string, unknown>;
  preconditions?: Array<Record<string, unknown>>;
  budget?: Record<string, unknown>;
  capabilities?: string[];
  expires_at?: number | null;
}
/** Re-validates the exact package binding immediately before a governed decision. */
export const getActionPackagePreflight = (packageId: string) => apiFetch<ActionPackagePreflight>(`/api/action-packages/${encodeURIComponent(packageId)}/preflight`);

export const createActionPackage = (workId: string, proposal: ActionPackageProposal, idempotencyKey: string) =>
  apiFetch<ActionPackage>(
    `/api/works/${encodeURIComponent(workId)}/action-packages`,
    { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify(proposal) },
  );

export interface ActionPackageDecisionBinding {
  expectedRevision: number;
  expectedPayloadHash: string;
}

/** A package from an older endpoint must never be approved by the governed UI. */
export const getActionPackageDecisionBinding = (item: ActionPackage): ActionPackageDecisionBinding | null => {
  if (typeof item.revision !== 'number' || !Number.isInteger(item.revision) || item.revision < 1) return null;
  if (typeof item.payload_hash !== 'string' || item.payload_hash.trim() === '') return null;
  return { expectedRevision: item.revision, expectedPayloadHash: item.payload_hash };
};

/** Only a valid canonical click-time preflight can supply a decision binding. */
export const getActionPackagePreflightDecisionBinding = (preflight: ActionPackagePreflight): ActionPackageDecisionBinding | null => {
  if (preflight.valid !== true) return null;
  if (typeof preflight.revision !== 'number' || !Number.isInteger(preflight.revision) || preflight.revision < 1) return null;
  if (typeof preflight.payload_hash !== 'string' || preflight.payload_hash.trim() === '') return null;
  return { expectedRevision: preflight.revision, expectedPayloadHash: preflight.payload_hash };
};

export const createActionPackageIdempotencyKey = (prefix = 'action-package-decision'): string => {
  const uuid = globalThis.crypto?.randomUUID?.();
  return uuid ? `${prefix}-${uuid}` : `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

/**
 * Approve an action package for GYO execution.
 *
 * CONTRACT: The approval API expects a JSON body with:
 *   - expected_revision: number (required) — optimistic concurrency guard
 *   - expected_payload_hash: string (required) — canonical integrity check
 *
 * The Idempotency-Key header prevents duplicate approvals.
 *
 * FAIL-CLOSED: If expectedRevision or expectedPayloadHash is missing/null,
 * the function throws an Error and does NOT make an API call. The caller
 * checks for this condition before calling this function and displays a clear UI message.
 *
 * The CTA wording in the UI is "Xác nhận cho GYO thực thi" — not "Phê duyệt nghiệp vụ".
 *
 * CP1 contract: the backend receives and validates this canonical body plus the
 * Idempotency-Key header. This client deliberately has no legacy success fallback.
 */
export const approveActionPackage = (
  id: string,
  options: { expectedRevision: number; expectedPayloadHash: string },
  idempotencyKey: string,
) => {
  // Fail-closed: both fields are required canonical values
  if (typeof options.expectedRevision !== 'number' || Number.isNaN(options.expectedRevision)) {
    throw new Error('expectedRevision is required (number) — cannot approve without concurrency guard');
  }
  if (typeof options.expectedPayloadHash !== 'string' || options.expectedPayloadHash.trim() === '') {
    throw new Error('expectedPayloadHash is required (string) — cannot approve without integrity check');
  }
  if (!idempotencyKey || idempotencyKey.trim() === '') {
    throw new Error('idempotencyKey is required — cannot approve without idempotency protection');
  }

  return apiFetch<ActionPackage>(
    `/api/action-packages/${encodeURIComponent(id)}/approve`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify({
        expected_revision: options.expectedRevision,
        expected_payload_hash: options.expectedPayloadHash,
      }),
    },
  );
};

export const denyActionPackage = (id: string, options: { expectedRevision: number; expectedPayloadHash: string }, idempotencyKey: string) =>
  apiFetch<ActionPackage>(`/api/action-packages/${encodeURIComponent(id)}/deny`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ expected_revision: options.expectedRevision, expected_payload_hash: options.expectedPayloadHash }),
  });

export const cancelActionPackage = (id: string, options: { expectedRevision: number; expectedPayloadHash: string }, idempotencyKey: string) =>
  apiFetch<ActionPackage>(`/api/action-packages/${encodeURIComponent(id)}/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ expected_revision: options.expectedRevision, expected_payload_hash: options.expectedPayloadHash }),
  });
