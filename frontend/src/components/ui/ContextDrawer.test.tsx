import React, { useRef, useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ContextDrawer } from './ContextDrawer';

const DrawerHarness: React.FC = () => {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  return <>
    <button ref={triggerRef} type="button" onClick={() => setOpen(true)}>Mở ngăn</button>
    <ContextDrawer open={open} title="Thông tin" onClose={() => setOpen(false)} returnFocusRef={triggerRef}>
      <button type="button">Hành động đầu</button>
      <button type="button">Hành động cuối</button>
    </ContextDrawer>
  </>;
};

describe('ContextDrawer', () => {
  it('locks scroll, closes with Escape, and restores focus', async () => {
    render(<DrawerHarness />);
    const trigger = screen.getByRole('button', { name: 'Mở ngăn' });
    trigger.focus();
    fireEvent.click(trigger);

    expect(screen.getByRole('dialog', { name: 'Thông tin' })).toBeDefined();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Đóng' }));
    expect(document.body.style.overflow).toBe('hidden');

    fireEvent.keyDown(document, { key: 'Escape' });

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull();
      expect(document.activeElement).toBe(trigger);
      expect(document.body.style.overflow).toBe('');
    });
  });

  it('keeps keyboard focus inside the drawer', () => {
    render(<DrawerHarness />);
    fireEvent.click(screen.getByRole('button', { name: 'Mở ngăn' }));

    const close = screen.getByRole('button', { name: 'Đóng' });
    const last = screen.getByRole('button', { name: 'Hành động cuối' });
    last.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(document.activeElement).toBe(close);

    close.focus();
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(last);
  });
});
