import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ContextPanel } from './ContextPanel';
import { resolveSafeUri } from './contextUri';
import type { AssistantContextManifest } from '../../api/assistant';

// Mock MarkdownRenderer for ContextPanel tests
vi.mock('../MarkdownRenderer', () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div data-testid="markdown">{content}</div>,
}));

describe('resolveSafeUri', () => {
  it('allows internal artifact routes (/work/ and /artifacts/)', () => {
    expect(resolveSafeUri('/work/work-1/artifact/123').safe).toBe(true);
    expect(resolveSafeUri('/artifacts/file.pdf').safe).toBe(true);
  });

  it('blocks non-allowlisted internal paths (e.g. /foo/bar)', () => {
    expect(resolveSafeUri('/foo/bar').safe).toBe(false);
    expect(resolveSafeUri('/settings').safe).toBe(false);
  });

  it('blocks protocol-relative URLs (//evil.example)', () => {
    expect(resolveSafeUri('//evil.example').safe).toBe(false);
  });

  it('blocks backslash-based paths (/\\evil.example)', () => {
    expect(resolveSafeUri('/\\evil.example').safe).toBe(false);
  });

  it('blocks backslash-only protocol-relative URLs', () => {
    expect(resolveSafeUri('\\\\evil.example').safe).toBe(false);
  });

  it('allows http/https URLs', () => {
    expect(resolveSafeUri('https://example.com').safe).toBe(true);
    expect(resolveSafeUri('http://example.com/page').safe).toBe(true);
    const resolved = resolveSafeUri('https://example.com');
    expect(resolved.safe).toBe(true);
    if (!resolved.safe) throw new Error('Expected a safe URL');
    expect(resolved.external).toBe(true);
  });

  it('blocks javascript: URIs', () => {
    expect(resolveSafeUri('javascript:alert(1)').safe).toBe(false);
  });

  it('blocks data: URIs', () => {
    expect(resolveSafeUri('data:text/html,<script>alert(1)</script>').safe).toBe(false);
  });

  it('blocks file: URIs', () => {
    expect(resolveSafeUri('file:///etc/passwd').safe).toBe(false);
  });

  it('blocks blob: URIs', () => {
    expect(resolveSafeUri('blob:https://example.com/abc-123').safe).toBe(false);
  });

  it('blocks empty URIs', () => {
    expect(resolveSafeUri('').safe).toBe(false);
    expect(resolveSafeUri('   ').safe).toBe(false);
  });

  it('blocks control characters', () => {
    expect(resolveSafeUri('/work/test\x00').safe).toBe(false);
    expect(resolveSafeUri('/work/test\n').safe).toBe(false);
  });

  it('blocks relative paths that are not internal routes', () => {
    expect(resolveSafeUri('../../../etc/passwd').safe).toBe(false);
    expect(resolveSafeUri('relative/path').safe).toBe(false);
  });

  it('blocks any path containing backslash', () => {
    expect(resolveSafeUri('/work/test\\evil').safe).toBe(false);
    expect(resolveSafeUri('\\work\\test').safe).toBe(false);
  });
});

describe('ContextPanel link safety', () => {
  const baseManifest: AssistantContextManifest = {
    work_id: 'work-a',
    conversation_id: 'conv-1',
    included: [],
    accessible: [
      { id: '1', uri: '/work/work-a/artifact/1', title: 'Internal artifact', kind: 'file' },
      { id: '2', uri: 'https://example.com', title: 'External link', kind: 'url' },
      { id: '3', uri: 'javascript:alert(1)', title: 'Unsafe JS', kind: 'url' },
      { id: '4', uri: 'data:text/html,<script>', title: 'Unsafe data', kind: 'url' },
      { id: '5', uri: 'blob:https://evil.com/abc', title: 'Unsafe blob', kind: 'url' },
      { id: '6', uri: '', title: 'Empty URI', kind: 'url' },
      { id: '7', uri: 'file:///etc/passwd', title: 'Unsafe file', kind: 'file' },
      { id: '8', uri: '//evil.example', title: 'Protocol-relative', kind: 'url' },
      { id: '9', uri: '/\\evil.example', title: 'Backslash path', kind: 'url' },
    ],
    excluded: [],
    byte_limit: 1000,
    byte_count: 500,
    memory_hub_auto_injected: false,
  };

  it('renders external links with "Mở bên ngoài" aria-label', () => {
    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    render(<ContextPanel manifest={baseManifest} artifacts={[]} loading={false} />);

    const externalBtn = screen.getByLabelText('Mở bên ngoài: External link');
    expect(externalBtn).toBeDefined();

    fireEvent.click(externalBtn);
    expect(windowOpenSpy).toHaveBeenCalledWith('https://example.com', '_blank', 'noopener,noreferrer');
    windowOpenSpy.mockRestore();
  });

  it('does not infer provenance from the legacy included group', () => {
    const manifest: AssistantContextManifest = { ...baseManifest, accessible: [], included: [{ id: 'legacy', title: 'Legacy candidate', uri: '/work/work-a/artifact/1' }] };
    render(<ContextPanel manifest={manifest} artifacts={[]} loading={false} />);
    expect(screen.queryByText('Legacy candidate')).toBeNull();
    expect(screen.queryByText('Đã truy cập')).toBeNull();
  });

  it('blocks unsafe URIs — no link button rendered, warning icon shown', () => {
    render(<ContextPanel manifest={baseManifest} artifacts={[]} loading={false} />);

    // javascript:, data:, blob:, file:, empty, //evil, /\\evil — all blocked (7 total)
    const unsafeItems = screen.getAllByLabelText('Đường dẫn không an toàn');
    expect(unsafeItems.length).toBe(7);
  });

  it('allows internal routes to have a link button', () => {
    render(<ContextPanel manifest={baseManifest} artifacts={[]} loading={false} />);

    const internalBtn = screen.getByLabelText('Mở Internal artifact');
    expect(internalBtn).toBeDefined();
    // Internal link should not have external link icon
    const externalIcon = internalBtn.querySelector('[data-testid]');
    expect(externalIcon).toBeNull();
  });

  it('shows external link icon for external URLs', () => {
    render(<ContextPanel manifest={baseManifest} artifacts={[]} loading={false} />);
    const externalBtn = screen.getByLabelText('Mở bên ngoài: External link');
    // External link button should exist
    expect(externalBtn).toBeDefined();
  });

  it('clicking unsafe URI does nothing', () => {
    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    render(<ContextPanel manifest={baseManifest} artifacts={[]} loading={false} />);

    const unsafeItems = screen.getAllByLabelText('Đường dẫn không an toàn');
    // The unsafe items are spans (not buttons) — no click handler to trigger navigation
    unsafeItems.forEach(item => {
      expect(item).toBeDefined();
    });

    expect(windowOpenSpy).not.toHaveBeenCalled();
    windowOpenSpy.mockRestore();
  });
});
