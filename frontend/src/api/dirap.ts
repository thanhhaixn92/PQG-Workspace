import { apiFetch } from './client';

export interface DirapSourceFile {
  id: string;
  task_id: string;
  file_path: string;
  file_name: string;
  note?: string | null;
  attached_at: number;
}

export interface DirapWorkItem {
  task_id: string;
  session_id: string;
  title?: string | null;
  goal?: string | null;
  status: string;
  task_type: string;
  session_title?: string | null;
  workspace_path?: string | null;
  source_files: DirapSourceFile[];
  created_at: number;
  updated_at: number;
  duplicate: boolean;
}

export interface AuditEvent {
  id: string;
  session_id?: string | null;
  actor: string;
  action: string;
  target?: string | null;
  payload_json?: string | null;
  created_at: number;
}

export interface DirapWorkItemDetail {
  work_item: DirapWorkItem;
  audit_events: AuditEvent[];
}

export interface DirapWorkItemCreateRequest {
  session_id: string;
  title: string;
  goal?: string | null;
}

export interface DirapSourceFileAttachRequest {
  file_path: string;
  note?: string | null;
}

export const createWorkItem = async (
  request: DirapWorkItemCreateRequest,
  idempotencyKey?: string,
): Promise<DirapWorkItem> => {
  const headers: Record<string, string> = {};
  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }
  return apiFetch<DirapWorkItem>('/api/dirap/work-items', {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });
};

export const listWorkItems = async (params?: {
  session_id?: string;
  limit?: number;
  offset?: number;
}): Promise<DirapWorkItem[]> => {
  const searchParams = new URLSearchParams();
  if (params?.session_id) searchParams.append('session_id', params.session_id);
  if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());
  if (params?.offset !== undefined) searchParams.append('offset', params.offset.toString());

  const query = searchParams.toString();
  return apiFetch<DirapWorkItem[]>(`/api/dirap/work-items${query ? `?${query}` : ''}`);
};

export const getWorkItemDetail = async (taskId: string): Promise<DirapWorkItemDetail> => {
  return apiFetch<DirapWorkItemDetail>(`/api/dirap/work-items/${taskId}`);
};

export const attachSourceFile = async (
  taskId: string,
  request: DirapSourceFileAttachRequest,
): Promise<DirapSourceFile> => {
  return apiFetch<DirapSourceFile>(`/api/dirap/work-items/${taskId}/source-files`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
};

export interface DirapExtractionSummary {
  id: string;
  source_file_id: string;
  source_sha256: string;
  extracted_at: number;
  extractor_version: string;
  file_type: string;
  status: 'fresh' | 'stale';
  record_count: number;
}

export interface DirapExtractionRecord {
  id: string;
  seq: number;
  content: string;
  provenance?: string | null;
}

export interface DirapExtractionDetail {
  extraction: DirapExtractionSummary;
  records: DirapExtractionRecord[];
  total_records: number;
}

export const extractSourceFile = async (
  taskId: string,
  sourceFileId: string,
): Promise<DirapExtractionDetail> => {
  return apiFetch<DirapExtractionDetail>(
    `/api/dirap/work-items/${taskId}/source-files/${sourceFileId}/extract`,
    { method: 'POST' },
  );
};

export const listExtractions = async (
  taskId: string,
  sourceFileId: string,
): Promise<DirapExtractionSummary[]> => {
  return apiFetch<DirapExtractionSummary[]>(
    `/api/dirap/work-items/${taskId}/source-files/${sourceFileId}/extractions`,
  );
};

export const getExtractionDetail = async (
  taskId: string,
  sourceFileId: string,
  extractionId: string,
): Promise<DirapExtractionDetail> => {
  return apiFetch<DirapExtractionDetail>(
    `/api/dirap/work-items/${taskId}/source-files/${sourceFileId}/extractions/${extractionId}`,
  );
};

export type DirapKnowledgeStatus = 'draft' | 'review_pending' | 'active' | 'rejected';
// Tập đóng quyền hạn nguồn (Codex chốt hợp đồng dữ liệu); 'none' chỉ là mặc định, không dùng khi duyệt.
export type DirapKnowledgeAuthorityStatus = 'none' | 'regulatory' | 'organizational' | 'expert' | 'derived';
export type DirapKnowledgeAuthorityForApprove = Exclude<DirapKnowledgeAuthorityStatus, 'none'>;
export const DIRAP_AUTHORITY_OPTIONS: DirapKnowledgeAuthorityForApprove[] = [
  'regulatory',
  'organizational',
  'expert',
  'derived',
];

export interface DirapKnowledgeEvidence {
  id: string;
  knowledge_record_id: string;
  evidence_type: 'reviewer' | 'source_evidence' | 'calculation_evidence' | 'authority_evidence' | 'decision_reason';
  reference: string;
  note?: string | null;
  created_at: number;
}

export interface DirapKnowledgeRecord {
  id: string;
  task_id: string;
  session_id?: string | null;
  extraction_id: string;
  extraction_record_id: string;
  source_file_id: string;
  source_sha256: string;
  extractor_version: string;
  provenance?: string | null;
  content: string;
  status: DirapKnowledgeStatus;
  source_verification_state: 'unverified' | 'verified';
  calculation_verification_state: 'unverified' | 'verified';
  owner_acceptance_state: 'pending' | 'accepted' | 'rejected';
  authority_status: DirapKnowledgeAuthorityStatus;
  note?: string | null;
  created_at: number;
  updated_at: number;
  // Chỉ có trong GET chi tiết
  evidence?: DirapKnowledgeEvidence[];
}

export interface DirapKnowledgeRecordCreateRequest {
  extraction_id: string;
  extraction_record_id: string;
  note?: string | null;
}

export interface DirapKnowledgeSubmitRequest {
  note?: string | null;
}

export interface DirapKnowledgeApproveRequest {
  reviewer: string;
  source_evidence_reference: string;
  authority_status: DirapKnowledgeAuthorityForApprove;
  authority_reference: string;
  calculation_evidence_reference?: string | null;
  note?: string | null;
}

export interface DirapKnowledgeRejectRequest {
  reviewer: string;
  reason: string;
  note?: string | null;
}

export const createKnowledgeRecord = async (
  taskId: string,
  request: DirapKnowledgeRecordCreateRequest,
  idempotencyKey?: string,
): Promise<DirapKnowledgeRecord> => {
  const headers: Record<string, string> = {};
  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }
  return apiFetch<DirapKnowledgeRecord>(
    `/api/dirap/work-items/${taskId}/knowledge-records`,
    { method: 'POST', headers, body: JSON.stringify(request) },
  );
};

export const listKnowledgeRecords = async (
  taskId: string,
): Promise<DirapKnowledgeRecord[]> => {
  return apiFetch<DirapKnowledgeRecord[]>(`/api/dirap/work-items/${taskId}/knowledge-records`);
};

export const getKnowledgeRecordDetail = async (
  taskId: string,
  knowledgeRecordId: string,
): Promise<DirapKnowledgeRecord> => {
  return apiFetch<DirapKnowledgeRecord>(
    `/api/dirap/work-items/${taskId}/knowledge-records/${knowledgeRecordId}`,
  );
};

export const submitKnowledgeRecord = async (
  taskId: string,
  knowledgeRecordId: string,
  request: DirapKnowledgeSubmitRequest,
  idempotencyKey?: string,
): Promise<DirapKnowledgeRecord> => {
  const headers: Record<string, string> = {};
  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }
  return apiFetch<DirapKnowledgeRecord>(
    `/api/dirap/work-items/${taskId}/knowledge-records/${knowledgeRecordId}/submit`,
    { method: 'POST', headers, body: JSON.stringify(request) },
  );
};

export const approveKnowledgeRecord = async (
  taskId: string,
  knowledgeRecordId: string,
  request: DirapKnowledgeApproveRequest,
  idempotencyKey?: string,
): Promise<DirapKnowledgeRecord> => {
  const headers: Record<string, string> = {};
  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }
  return apiFetch<DirapKnowledgeRecord>(
    `/api/dirap/work-items/${taskId}/knowledge-records/${knowledgeRecordId}/review/approve`,
    { method: 'POST', headers, body: JSON.stringify(request) },
  );
};

export const rejectKnowledgeRecord = async (
  taskId: string,
  knowledgeRecordId: string,
  request: DirapKnowledgeRejectRequest,
  idempotencyKey?: string,
): Promise<DirapKnowledgeRecord> => {
  const headers: Record<string, string> = {};
  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }
  return apiFetch<DirapKnowledgeRecord>(
    `/api/dirap/work-items/${taskId}/knowledge-records/${knowledgeRecordId}/review/reject`,
    { method: 'POST', headers, body: JSON.stringify(request) },
  );
};

// ---------------------------------------------------------------------------
// DIRAP v3.0 Usability — policy v1 (chỉ đọc, không ghi kết quả)
// ---------------------------------------------------------------------------

// Sáu mục đích sử dụng chuẩn, duy nhất (theo USABILITY_POLICY_DECISION.md).
export type DirapUsabilityQueryType =
  | 'official_search'
  | 'exploratory_search'
  | 'analysis_input'
  | 'legal_review'
  | 'context_packaging'
  | 'memory_query';

export type DirapUsabilityState = 'usable' | 'partial_usable' | 'unusable';

export const DIRAP_USABILITY_QUERY_TYPES: DirapUsabilityQueryType[] = [
  'official_search',
  'exploratory_search',
  'analysis_input',
  'legal_review',
  'context_packaging',
  'memory_query',
];

export interface DirapUsabilityExclusion {
  dimension: string;
  required_state: string;
  actual_state: string;
  reason: string;
}

export interface DirapUsabilityResult {
  record_id: string;
  lifecycle_state: DirapKnowledgeStatus;
  query_type: DirapUsabilityQueryType;
  source_verification_state: 'unverified' | 'verified';
  calculation_verification_state: 'unverified' | 'verified';
  owner_acceptance_state: 'pending' | 'accepted' | 'rejected';
  authority_status: DirapKnowledgeAuthorityStatus;
  overall_usability_state: DirapUsabilityState;
  policy_version: 'v1';
  exclusions: DirapUsabilityExclusion[];
  // Chỉ gồm các mục đích đạt 'usable' (không gồm partial_usable) cho bản ghi này
  usable_for_query_types: DirapUsabilityQueryType[];
}

export const getKnowledgeUsability = async (
  taskId: string,
  knowledgeRecordId: string,
  queryType: DirapUsabilityQueryType,
): Promise<DirapUsabilityResult> => {
  return apiFetch<DirapUsabilityResult>(
    `/api/dirap/work-items/${taskId}/knowledge-records/${knowledgeRecordId}/usability?query_type=${encodeURIComponent(queryType)}`,
  );
};

// DIRAP v3.0 Controlled knowledge search — chỉ đọc, lọc theo chính sách v1
// ---------------------------------------------------------------------------

export interface DirapKnowledgeSearchResult {
  record_id: string;
  content_excerpt: string;
  provenance: string | null;
  lifecycle_state: DirapKnowledgeStatus;
  source_verification_state: 'unverified' | 'verified';
  calculation_verification_state: 'unverified' | 'verified';
  owner_acceptance_state: 'pending' | 'accepted' | 'rejected';
  authority_status: DirapKnowledgeAuthorityStatus;
  // 'content' | 'provenance' | 'both'
  matched_field: 'content' | 'provenance' | 'both';
  usability_state: DirapUsabilityState;
}

export interface DirapKnowledgeSearchResponse {
  query_type: DirapUsabilityQueryType;
  // Tổng số bản ghi sau so khớp + lọc chính sách, TRƯỚC phân trang
  total: number;
  limit: number;
  offset: number;
  results: DirapKnowledgeSearchResult[];
}

export const searchKnowledgeRecords = async (
  taskId: string,
  params: {
    q: string;
    queryType: DirapUsabilityQueryType;
    limit?: number;
    offset?: number;
  },
): Promise<DirapKnowledgeSearchResponse> => {
  const p = new URLSearchParams({
    q: params.q,
    query_type: params.queryType,
  });
  if (params.limit !== undefined) p.set('limit', String(params.limit));
  if (params.offset !== undefined) p.set('offset', String(params.offset));
  return apiFetch<DirapKnowledgeSearchResponse>(
    `/api/dirap/work-items/${taskId}/knowledge-records/search?${p.toString()}`,
  );
};
