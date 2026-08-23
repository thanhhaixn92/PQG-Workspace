import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ApiError } from '../api/client';
import { EditorPanel } from './EditorPanel';
import { useHermesStore } from '../store/store';
import * as filesApi from '../api/files';

vi.mock('../api/files', () => ({
  fetchFileContent: vi.fn(),
  fetchFileTree: vi.fn(),
  saveFileContent: vi.fn(),
}));

vi.mock('@monaco-editor/react', () => ({
  default: ({ value, onChange }: any) => (
    <textarea
      data-testid="monaco-mock"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));

describe('EditorPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.mocked(filesApi.fetchFileTree).mockResolvedValue({ tree: [], truncated: false });
    useHermesStore.setState({
      activeSessionId: 'session-1',
      openFiles: ['test.txt'],
      activeFile: 'test.txt',
      fileContents: { 'test.txt': 'initial content' },
      fileMetadata: { 'test.txt': { mtime: 100, size: 15 } },
      dirtyFiles: new Set(),
      auditRefreshVersion: 0,
    });
  });

  it('renders correctly with open file', () => {
    render(<EditorPanel />);
    expect(screen.getByText('test.txt')).toBeDefined();
    expect(screen.getByRole('tab', { name: 'test.txt' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByText('Đã lưu')).toBeDefined();
    expect(screen.getByTestId('monaco-mock')).toHaveProperty('value', 'initial content');
  });

  it('marks file as dirty on edit', () => {
    render(<EditorPanel />);
    const editor = screen.getByTestId('monaco-mock');

    act(() => {
      fireEvent.change(editor, { target: { value: 'new content' } });
    });

    expect(useHermesStore.getState().dirtyFiles.has('test.txt')).toBe(true);
    expect(useHermesStore.getState().fileContents['test.txt']).toBe('new content');
    expect(screen.getByText('Chưa lưu')).toBeDefined();
  });

  it('debounces save, marks clean, refreshes audit and file tree', async () => {
    vi.mocked(filesApi.saveFileContent).mockResolvedValue({ status: 'saved', mtime: 200, size: 7 });

    render(<EditorPanel />);
    const editor = screen.getByTestId('monaco-mock');

    act(() => {
      fireEvent.change(editor, { target: { value: 'save me' } });
    });

    await waitFor(() => {
      expect(filesApi.saveFileContent).toHaveBeenCalledWith('session-1', 'test.txt', 'save me', 100, false);
      expect(useHermesStore.getState().dirtyFiles.has('test.txt')).toBe(false);
    }, { timeout: 2200 });
    expect(screen.getByText('Đã lưu')).toBeDefined();
    expect(useHermesStore.getState().fileMetadata['test.txt']).toEqual({ mtime: 200, size: 7 });
    expect(useHermesStore.getState().auditRefreshVersion).toBe(1);
    expect(filesApi.fetchFileTree).toHaveBeenCalledWith('session-1');
  });

  it('displays error gracefully if save fails', async () => {
    vi.mocked(filesApi.saveFileContent).mockRejectedValue(new Error('Save failed'));

    render(<EditorPanel />);
    const editor = screen.getByTestId('monaco-mock');

    act(() => {
      fireEvent.change(editor, { target: { value: 'fail me' } });
    });

    await waitFor(() => {
      expect(screen.getByText(/Không lưu được test.txt: Save failed/)).toBeDefined();
    }, { timeout: 2200 });
    expect(screen.getByText('Lỗi lưu')).toBeDefined();
  });

  it('shows conflict actions when backend reports external file change', async () => {
    vi.mocked(filesApi.saveFileContent).mockRejectedValue(new ApiError(409, 'File changed on disk'));

    render(<EditorPanel />);
    const editor = screen.getByTestId('monaco-mock');

    act(() => {
      fireEvent.change(editor, { target: { value: 'conflicting edit' } });
    });

    await waitFor(() => {
      expect(screen.getByText(/có thể đã thay đổi bên ngoài app/)).toBeDefined();
      expect(screen.getByText('Tải lại')).toBeDefined();
      expect(screen.getByText('Lưu đè')).toBeDefined();
    }, { timeout: 2200 });
  });

  it('supports manual save', async () => {
    vi.mocked(filesApi.saveFileContent).mockResolvedValue({ status: 'saved', mtime: 201, size: 11 });
    useHermesStore.setState({
      dirtyFiles: new Set(['test.txt']),
      fileContents: { 'test.txt': 'manual save' },
    });

    render(<EditorPanel />);
    fireEvent.click(screen.getByTitle('Lưu tệp'));

    await waitFor(() => {
      expect(filesApi.saveFileContent).toHaveBeenCalledWith('session-1', 'test.txt', 'manual save', 100, false);
    });
  });

  it('restores the last saved content after confirmation', () => {
    render(<EditorPanel />);
    const editor = screen.getByTestId('monaco-mock');

    act(() => {
      fireEvent.change(editor, { target: { value: 'unsaved edit' } });
    });

    fireEvent.click(screen.getByTitle('Khôi phục bản đã lưu'));

    expect(window.confirm).toHaveBeenCalled();
    expect(useHermesStore.getState().fileContents['test.txt']).toBe('initial content');
    expect(useHermesStore.getState().dirtyFiles.has('test.txt')).toBe(false);
  });

  it('confirms before closing a dirty file', () => {
    useHermesStore.setState({
      dirtyFiles: new Set(['test.txt']),
    });

    render(<EditorPanel />);
    fireEvent.click(screen.getByTitle('Đóng tệp'));

    expect(window.confirm).toHaveBeenCalledWith('Tệp này còn thay đổi chưa lưu. Đóng tệp và bỏ thay đổi?');
    expect(useHermesStore.getState().openFiles).toEqual([]);
  });
});
