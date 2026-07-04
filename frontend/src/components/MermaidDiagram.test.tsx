import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MermaidDiagram } from './MermaidDiagram';
import mermaid from 'mermaid';

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    parse: vi.fn(),
    render: vi.fn(),
  },
}));

describe('MermaidDiagram', () => {
  beforeEach(() => {
    vi.mocked(mermaid.initialize).mockClear();
    vi.mocked(mermaid.parse).mockReset();
    vi.mocked(mermaid.render).mockReset();
  });

  it('khởi tạo Mermaid với chế độ bảo mật strict khi render diagram', async () => {
    vi.mocked(mermaid.parse).mockResolvedValue(true as any);
    vi.mocked(mermaid.render).mockResolvedValue({
      svg: '<svg id="mock-svg">valid</svg>',
      bindFunctions: undefined,
      diagramType: 'flowchart-v2',
    });

    render(<MermaidDiagram content="graph TD;\n A-->B;" />);

    await waitFor(() => {
      expect(mermaid.initialize).toHaveBeenCalledWith(expect.objectContaining({
        securityLevel: 'strict',
        startOnLoad: false,
      }));
    });
  });

  it('hiển thị sơ đồ Mermaid hợp lệ', async () => {
    const validSyntax = 'graph TD;\n A-->B;';
    const mockSvg = '<svg id="mock-svg">valid</svg>';

    vi.mocked(mermaid.parse).mockResolvedValue(true as any);
    vi.mocked(mermaid.render).mockResolvedValue({
      svg: mockSvg,
      bindFunctions: undefined,
      diagramType: 'flowchart-v2',
    });

    render(<MermaidDiagram content={validSyntax} />);

    await waitFor(() => {
      const container = document.querySelector('.mermaid-content');
      expect(container?.innerHTML).toContain(mockSvg);
    });

    expect(screen.getByTitle('Xuất SVG')).toBeDefined();
    expect(screen.getByTitle('Xuất PNG')).toBeDefined();
  });

  it('hiển thị fallback thân thiện khi sai cú pháp', async () => {
    const invalidSyntax = 'invalid mermaid';

    vi.mocked(mermaid.parse).mockRejectedValue(new Error('Parse error'));

    render(<MermaidDiagram content={invalidSyntax} />);

    await waitFor(() => {
      expect(screen.getByText('Sơ đồ cần sửa cú pháp')).toBeDefined();
      expect(screen.getByText(/Chi tiết: Parse error/)).toBeDefined();
      expect(screen.getByText(invalidSyntax)).toBeDefined();
    });

    expect(screen.queryByTitle('Xuất SVG')).toBeNull();
  });
});
