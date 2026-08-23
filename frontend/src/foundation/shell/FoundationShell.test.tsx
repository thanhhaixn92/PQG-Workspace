import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FoundationShell } from './FoundationShell';

describe('FoundationShell', () => {
  it('provides the stable Foundation root without changing legacy app-layout styling', () => {
    const { container } = render(<FoundationShell className="assistant-collapsed"><main>Nội dung</main></FoundationShell>);
    const shell = container.querySelector('[data-foundation-shell="true"]');
    expect(shell).toBeDefined();
    expect(shell?.className).toContain('app-layout');
    expect(shell?.className).toContain('foundation-shell');
    expect(shell?.className).toContain('assistant-collapsed');
  });
});
