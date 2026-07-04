import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchFileContent } from '../api/files';
import { useHermesStore } from '../store/store';
import { MarkdownRenderer } from './MarkdownRenderer';

vi.mock('../api/files', () => ({
  fetchFileContent: vi.fn(),
}));

vi.mock('./MermaidDiagram', () => ({
  MermaidDiagram: ({ content }: { content: string }) => (
    <div data-testid="mermaid-lazy">Mermaid: {content}</div>
  ),
}));

describe('MarkdownRenderer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useHermesStore.setState({
      sessions: [],
      activeSessionId: null,
      sidebarTab: 'sessions',
      openFiles: [],
      activeFile: null,
      fileContents: {},
      fileMetadata: {},
      dirtyFiles: new Set(),
    });
  });

  it('renders normal markdown without Mermaid', () => {
    render(<MarkdownRenderer content={`## Xin chào

- Một mục`} />);

    expect(screen.getByText('Xin chào')).toBeDefined();
    expect(screen.getByText('Một mục')).toBeDefined();
  });

  it('renders inline code as code, not a block pre', () => {
    const { container } = render(<MarkdownRenderer content={'Cài gói `python-docx` trước khi chạy.'} />);

    expect(screen.getByText('python-docx').tagName).toBe('CODE');
    expect(container.querySelector('pre')).toBeNull();
  });

  it('renders normal code blocks without nested pre tags', () => {
    const { container } = render(<MarkdownRenderer content={'```python\nprint("ok")\n```'} />);

    expect(container.querySelectorAll('pre')).toHaveLength(1);
    expect(container.querySelector('pre pre')).toBeNull();
    expect(screen.getByText('print("ok")')).toBeDefined();
  });

  it('renders desktop-local-file blocks as a file card and does not open docx as text', () => {
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
    useHermesStore.setState({
      activeSessionId: 's1',
      sessions: [{ id: 's1', title: 'S1', workspace_path: 'C:\\Users\\dtron\\Documents', created_at: 1 }],
    });

    const { container } = render(
      <MarkdownRenderer
        content={'```desktop-local-file\n{"localPath":"C:\\\\Users\\\\dtron\\\\Documents\\\\report.docx","fileName":"report.docx"}\n```'}
      />,
    );

    expect(screen.getByText('report.docx')).toBeDefined();
    expect(screen.getByText('C:\\Users\\dtron\\Documents\\report.docx')).toBeDefined();
    expect(screen.getByText('Trong workspace')).toBeDefined();
    expect(screen.queryByText('Mở trong tab Tệp')).toBeNull();
    expect(screen.queryByText(/localPath/)).toBeNull();
    expect(container.querySelector('pre')).toBeNull();

    fireEvent.click(screen.getByText('Copy đường dẫn'));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('C:\\Users\\dtron\\Documents\\report.docx');
  });

  it('renders content quality metadata on file cards', () => {
    useHermesStore.setState({
      activeSessionId: 's1',
      sessions: [{ id: 's1', title: 'S1', workspace_path: 'C:\\Users\\dtron\\Documents', created_at: 1 }],
    });

    render(
      <MarkdownRenderer
        content={'```desktop-local-file\n{"localPath":"C:\\\\Users\\\\dtron\\\\Documents\\\\article.html","fileName":"article.html","contentQuality":{"status":"needs_review","label":"Thiếu nguồn","issues":["Bài viết thiếu nguồn tham khảo hoặc link nguồn cụ thể."]}}\n```'}
      />,
    );

    expect(screen.getByText('article.html')).toBeDefined();
    expect(screen.getByText('Thiếu nguồn')).toBeDefined();
    expect(screen.getByText('Bài viết thiếu nguồn tham khảo hoặc link nguồn cụ thể.')).toBeDefined();
  });

  it('opens workspace text files through the backend file API', async () => {
    vi.mocked(fetchFileContent).mockResolvedValue({ content: '# Báo cáo', mtime: 10, size: 8 });
    useHermesStore.setState({
      activeSessionId: 's1',
      sessions: [{ id: 's1', title: 'S1', workspace_path: 'C:\\Users\\dtron\\Documents', created_at: 1 }],
    });

    render(
      <MarkdownRenderer
        content={'```desktop-local-file\n{"localPath":"C:\\\\Users\\\\dtron\\\\Documents\\\\report.md","fileName":"report.md"}\n```'}
      />,
    );

    fireEvent.click(screen.getByText('Mở trong tab Tệp'));

    await waitFor(() => {
      expect(fetchFileContent).toHaveBeenCalledWith('s1', 'report.md');
      expect(useHermesStore.getState().activeFile).toBe('report.md');
      expect(useHermesStore.getState().sidebarTab).toBe('files');
    });
  });

  it('shows a copy error when clipboard is unavailable', async () => {
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockRejectedValue(new Error('blocked')),
      },
    });

    render(
      <MarkdownRenderer
        content={'```desktop-local-file\n{"localPath":"C:\\\\Users\\\\dtron\\\\Documents\\\\report.docx","fileName":"report.docx"}\n```'}
      />,
    );

    fireEvent.click(screen.getByText('Copy đường dẫn'));

    await waitFor(() => {
      expect(screen.getByText('Không copy được, hãy bôi đen đường dẫn để copy thủ công.')).toBeDefined();
    });
  });

  it('lazy-renders Mermaid blocks without nested pre tags', async () => {
    const { container } = render(<MarkdownRenderer content={'```mermaid\ngraph TD; A-->B;\n```'} />);

    expect((await screen.findByTestId('mermaid-lazy')).textContent).toContain('graph TD; A-->B;');
    expect(container.querySelector('pre')).toBeNull();
  });
});
