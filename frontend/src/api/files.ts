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
}

export interface SaveFileResponse {
  status: 'saved';
  mtime: number;
  size: number;
}

export async function fetchFileTree(sessionId: string): Promise<FileTreeResponse> {
  return apiFetch<FileTreeResponse>(`/api/sessions/${sessionId}/files/tree`);
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
): Promise<SaveFileResponse> {
  const url = `/api/sessions/${sessionId}/files/content?path=${encodeURIComponent(filePath)}`;
  return apiFetch<SaveFileResponse>(url, {
    method: 'PUT',
    body: JSON.stringify({ content, expected_mtime: expectedMtime, force }),
  });
}
