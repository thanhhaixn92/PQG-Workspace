import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FileExplorer } from './FileExplorer';
import { useHermesStore } from '../store/store';
import * as filesApi from '../api/files';

vi.mock('../api/files', () => ({
  fetchFileTree: vi.fn(),
  fetchFileContent: vi.fn(),
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
    expect(screen.getByText('Chưa chọn không gian làm việc')).toBeDefined();
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
});
