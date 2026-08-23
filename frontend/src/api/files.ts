import { apiFetch } from './client';

export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  too_large?: boolean;
  children?: FileNode[];
}

export interface FileTreeResponse {
  tree: FileNode[];
  truncated: boolean;
}

export interface FileContentResponse {
  content: string;
  mtime: number;
  size: number;
  hash?: string;
}

export interface SaveFileResponse {
  status: 'saved';
  mtime: number;
  size: number;
  hash?: string;
}

export interface ImportedDocument {
  id: string;
  session_id: string;
  relative_path: string;
  kind: 'imported_file' | 'created_text_file';
  sha256: string;
  size_bytes: number;
  created_at: number;
  duplicate: boolean;
}

const toHex = (bytes: Uint8Array): string =>
  Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');

export async function importDocument(sessionId: string, file: File, idempotencyKey: string): Promise<ImportedDocument> {
  if (!globalThis.crypto?.subtle) throw new Error('Trình duyệt không hỗ trợ kiểm tra toàn vẹn tệp.');
  const body = await file.arrayBuffer();
  const digest = toHex(new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', body)));
  return apiFetch<ImportedDocument>(`/api/sessions/${sessionId}/documents/import`, {
    method: 'POST',
    headers: {
      'Content-Type': file.type || 'application/octet-stream',
      'Idempotency-Key': idempotencyKey,
      'X-File-Name': encodeURIComponent(file.name),
      'X-Content-SHA256': digest,
    },
    body,
  });
}

export async function createManagedTextFile(
  sessionId: string,
  relativePath: string,
  content: string,
  idempotencyKey: string,
): Promise<ImportedDocument> {
  return apiFetch<ImportedDocument>(`/api/sessions/${sessionId}/documents/files`, {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ relative_path: relativePath, content }),
  });
}

export async function createManagedFolder(
  sessionId: string,
  relativePath: string,
  idempotencyKey: string,
): Promise<{ relative_path: string; duplicate: boolean }> {
  return apiFetch(`/api/sessions/${sessionId}/documents/folders`, {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ relative_path: relativePath }),
  });
}

export async function fetchFileTree(sessionId: string, grouped = false): Promise<FileTreeResponse> {
  return apiFetch<FileTreeResponse>(`/api/sessions/${sessionId}/files/tree${grouped ? '?grouped=true' : ''}`);
}

export async function fetchFileContent(sessionId: string, filePath: string): Promise<FileContentResponse> {
  const url = `/api/sessions/${sessionId}/files/content?path=${encodeURIComponent(filePath)}`;
  return apiFetch<FileContentResponse>(url);
}

export async function saveFileContent(
  sessionId: string,
  filePath: string,
  content: string,
  expectedMtime?: number,
  force = false,
  expectedHash?: string,
): Promise<SaveFileResponse> {
  const url = `/api/sessions/${sessionId}/files/content?path=${encodeURIComponent(filePath)}`;
  return apiFetch<SaveFileResponse>(url, {
    method: 'PUT',
    body: JSON.stringify({ content, expected_mtime: expectedMtime, expected_hash: expectedHash, force }),
  });
}
