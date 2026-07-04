import React, { useEffect, useRef, useState } from 'react';
import { Download, AlertCircle } from 'lucide-react';

type MermaidApi = typeof import('mermaid').default;

let mermaidPromise: Promise<MermaidApi> | null = null;

async function loadMermaid(): Promise<MermaidApi> {
  if (!mermaidPromise) {
    mermaidPromise = import('mermaid').then(module => {
      const mermaid = module.default;
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'dark',
      });
      return mermaid;
    });
  }

  return mermaidPromise;
}

interface MermaidDiagramProps {
  content: string;
}

export const MermaidDiagram: React.FC<MermaidDiagramProps> = ({ content }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const id = useRef(`mermaid-${Math.random().toString(36).slice(2, 11)}`);

  useEffect(() => {
    let mounted = true;

    const renderDiagram = async () => {
      try {
        setError(null);
        setSvgContent(null);

        const mermaid = await loadMermaid();
        await mermaid.parse(content, { suppressErrors: false });

        const { svg, bindFunctions } = await mermaid.render(id.current, content);
        if (!mounted) return;

        setSvgContent(svg);
        if (bindFunctions && containerRef.current) {
          bindFunctions(containerRef.current);
        }
      } catch (err) {
        if (!mounted) return;

        const message = err instanceof Error
          ? err.message
          : 'Không hiển thị được sơ đồ Mermaid';
        setError(message);
        setSvgContent(null);
      }
    };

    void renderDiagram();

    return () => {
      mounted = false;
    };
  }, [content]);

  const handleExportSVG = () => {
    if (!svgContent) return;

    const blob = new Blob([svgContent], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `diagram-${id.current}.svg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleExportPNG = () => {
    if (!svgContent) return;

    const img = new Image();
    const svg64 = btoa(unescape(encodeURIComponent(svgContent)));

    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);

      const pngUrl = canvas.toDataURL('image/png');
      const a = document.createElement('a');
      a.href = pngUrl;
      a.download = `diagram-${id.current}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    };

    img.src = `data:image/svg+xml;base64,${svg64}`;
  };

  if (error) {
    return (
      <div className="mermaid-fallback" style={{ border: '1px solid var(--border)', borderRadius: '4px', padding: '1rem', margin: '1rem 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--warning-primary)', marginBottom: '0.5rem' }}>
          <AlertCircle size={16} />
          <strong>Sơ đồ cần sửa cú pháp</strong>
        </div>
        <pre style={{ margin: 0, padding: '0.5rem', background: 'var(--bg-secondary)', borderRadius: '4px', fontSize: '0.85em', overflowX: 'auto' }}>
          <code>{content}</code>
        </pre>
        <div style={{ marginTop: '0.5rem', fontSize: '0.85em', color: 'var(--text-secondary)' }}>
          Mermaid chưa thể hiển thị khối này. Nội dung gốc được giữ lại để bạn sửa hoặc thử lại. Chi tiết: {error}
        </div>
      </div>
    );
  }

  return (
    <div className="mermaid-container" style={{ position: 'relative', border: '1px solid var(--border)', borderRadius: '4px', padding: '1rem', margin: '1rem 0', background: 'var(--bg-secondary)' }}>
      {svgContent ? (
        <>
          <div className="mermaid-actions" style={{ position: 'absolute', top: '0.5rem', right: '0.5rem', display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={handleExportSVG}
              className="hermes-button"
              style={{ padding: '4px 8px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
              title="Xuất SVG"
            >
              <Download size={12} /> SVG
            </button>
            <button
              onClick={handleExportPNG}
              className="hermes-button"
              style={{ padding: '4px 8px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
              title="Xuất PNG"
            >
              <Download size={12} /> PNG
            </button>
          </div>
          <div
            ref={containerRef}
            className="mermaid-content"
            style={{ display: 'flex', justifyContent: 'center', overflowX: 'auto' }}
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        </>
      ) : (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
          Đang hiển thị sơ đồ...
        </div>
      )}
    </div>
  );
};
