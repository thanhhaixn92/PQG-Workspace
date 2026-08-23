import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FileExplorer } from './FileExplorer';
import { useHermesStore } from '../store/store';
import * as filesApi from '../api/files';
import { filterTestDataNodes } from './FileExplorer';

vi.mock('../api/files', () => ({
  fetchFileTree: vi.fn(),
  fetchFileContent: vi.fn(),
  importDocument: vi.fn(),
  createManagedTextFile: vi.fn(),
  createManagedFolder: vi.fn(),
}));

describe('FileExplorer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useHermesStore.setState({
      activeSessionId: 'session-1',
      fileTree: [],
      openFiles: [],
      activeFile: null,
      fileContents: {},
      fileMetadata: {},
      dirtyFiles: new Set(),
    });
  });

  it('renders empty tree state', async () => {
    vi.mocked(filesApi.fetchFileTree).mockResolvedValue({ tree: [], truncated: false });

    render(<FileExplorer />);

    await waitFor(() => {
      expect(screen.getByText('Không gian làm việc đang trống')).toBeDefined();
    });
  });

  it('shows guided state when no session is selected', () => {
    useHermesStore.setState({ activeSessionId: null, fileTree: [] });
    render(<FileExplorer />);
    expect(screen.getByText('Chưa chọn Công việc')).toBeDefined();
  });

  it('opens a file and stores metadata', async () => {
    vi.mocked(filesApi.fetchFileTree).mockResolvedValue({
      tree: [{ name: 'note.txt', path: 'note.txt', type: 'file' }],
      truncated: false,
    });
    vi.mocked(filesApi.fetchFileContent).mockResolvedValue({
      content: 'hello',
      mtime: 123,
      size: 5,
    });

    render(<FileExplorer />);

    await screen.findByText('note.txt');
    act(() => {
      fireEvent.click(screen.getByText('note.txt'));
    });

    await waitFor(() => {
      expect(useHermesStore.getState().fileContents['note.txt']).toBe('hello');
      expect(useHermesStore.getState().fileMetadata['note.txt']).toEqual({ mtime: 123, size: 5 });
    });
  });

  it('handles load failure gracefully', async () => {
    vi.mocked(filesApi.fetchFileTree).mockRejectedValue(new Error('Network error'));

    render(<FileExplorer />);

    await waitFor(() => {
      expect(screen.getByText(/Không tải được cây tệp/)).toBeDefined();
      expect(screen.getByText(/Network error/)).toBeDefined();
    });
  });

  it('displays error when reading oversized or binary file fails', async () => {
    vi.mocked(filesApi.fetchFileTree).mockResolvedValue({
      tree: [{ name: 'large.bin', path: 'large.bin', type: 'file' }],
      truncated: false,
    });
    vi.mocked(filesApi.fetchFileContent).mockRejectedValue(new Error('Binary files are not supported'));

    render(<FileExplorer />);

    await waitFor(() => {
      expect(screen.getByText('large.bin')).toBeDefined();
    });

    act(() => {
      fireEvent.click(screen.getByText('large.bin'));
    });

    await waitFor(() => {
      expect(screen.getByText(/Không đọc được tệp large.bin/)).toBeDefined();
      expect(screen.getByText(/Binary files are not supported/)).toBeDefined();
    });
  });

  it('blocks opening files marked as too_large natively', async () => {
    vi.mocked(filesApi.fetchFileTree).mockResolvedValue({
      tree: [{ name: 'huge.txt', path: 'huge.txt', type: 'file', too_large: true }],
      truncated: false,
    });

    render(<FileExplorer />);

    await waitFor(() => {
      expect(screen.getByText('huge.txt')).toBeDefined();
    });

    act(() => {
      fireEvent.click(screen.getByText('huge.txt'));
    });

    expect(filesApi.fetchFileContent).not.toHaveBeenCalled();
    expect(screen.getByText(/tệp quá lớn/)).toBeDefined();
  });

  it('ignores file content that returns after the active session changed', async () => {
    let resolveContent!: (value: { content: string; mtime: number; size: number; hash: string }) => void;
    vi.mocked(filesApi.fetchFileTree).mockResolvedValue({
      tree: [{ name: 'old.txt', path: 'old.txt', type: 'file' }],
      truncated: false,
    });
    vi.mocked(filesApi.fetchFileContent).mockReturnValue(new Promise(resolve => {
      resolveContent = resolve;
    }));

    render(<FileExplorer />);
    fireEvent.click(await screen.findByText('old.txt'));
    act(() => useHermesStore.getState().setActiveSession('session-2'));
    resolveContent({ content: 'session one', mtime: 1, size: 11, hash: 'old-hash' });

    await waitFor(() => expect(filesApi.fetchFileContent).toHaveBeenCalled());
    expect(useHermesStore.getState().openFiles).toEqual([]);
    expect(useHermesStore.getState().fileContents['old.txt']).toBeUndefined();
  });

  it('imports a selected file then refreshes the document tree', async () => {
    vi.mocked(filesApi.fetchFileTree).mockResolvedValue({ tree: [], truncated: false });
    vi.mocked(filesApi.importDocument).mockResolvedValue({
      id: 'artifact-1', session_id: 'session-1', relative_path: 'inputs/source.txt',
      kind: 'imported_file', sha256: 'hash', size_bytes: 5, created_at: 1, duplicate: false,
    });
    render(<FileExplorer />);
    await waitFor(() => expect(filesApi.fetchFileTree).toHaveBeenCalledTimes(1));
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['hello'], 'source.txt', { type: 'text/plain' });
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => expect(filesApi.importDocument).toHaveBeenCalledWith('session-1', file, expect.any(String)));
    await waitFor(() => expect(filesApi.fetchFileTree).toHaveBeenCalledTimes(2));
  });

  it('creates a managed text file from the end-user form', async () => {
    vi.mocked(filesApi.fetchFileTree).mockResolvedValue({ tree: [], truncated: false });
    vi.mocked(filesApi.createManagedTextFile).mockResolvedValue({
      id: 'created-1', session_id: 'session-1', relative_path: 'inputs/note.txt',
      kind: 'created_text_file', sha256: 'hash', size_bytes: 5, created_at: 1, duplicate: false,
    });
    render(<FileExplorer />);
    fireEvent.click(screen.getByTitle('Tạo tệp văn bản'));
    fireEvent.change(screen.getByLabelText('Tên tài liệu mới'), { target: { value: 'note.txt' } });
    fireEvent.change(screen.getByLabelText('Nội dung tệp mới'), { target: { value: 'hello' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo' }));
    await waitFor(() => expect(filesApi.createManagedTextFile).toHaveBeenCalledWith(
      'session-1', 'note.txt', 'hello', expect.any(String),
    ));
  });

  it('hides only known UAT/test markers from the normal grouped document view', () => {
    expect(filterTestDataNodes([
      { name: 'inputs', path: 'inputs', type: 'directory' },
      { name: 'uat-codex-run', path: 'uat-codex-run', type: 'directory' },
      { name: 'meeting-notes.md', path: 'meeting-notes.md', type: 'file' },
    ]).map(node => node.name)).toEqual(['inputs', 'meeting-notes.md']);
  });
});
