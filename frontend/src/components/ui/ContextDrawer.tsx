import React, { useEffect, useId, useRef } from 'react';

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

type ContextDrawerProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  returnFocusRef?: React.RefObject<HTMLElement | null>;
  children: React.ReactNode;
};

export const ContextDrawer: React.FC<ContextDrawerProps> = ({
  open,
  title,
  onClose,
  returnFocusRef,
  children,
}) => {
  const titleId = useId();
  const panelRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    const returnFocusElement = returnFocusRef?.current;
    document.body.style.overflow = 'hidden';
    closeButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;

      const focusable = Array.from(
        panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [],
      ).filter(element => !element.hasAttribute('disabled') && element.getAttribute('aria-hidden') !== 'true');
      if (focusable.length === 0) {
        event.preventDefault();
        panelRef.current?.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = previousOverflow;
      returnFocusElement?.focus();
    };
  }, [onClose, open, returnFocusRef]);

  if (!open) return null;

  return (
    <div className="context-drawer-layer">
      <div className="context-drawer-backdrop" aria-hidden="true" onMouseDown={onClose} />
      <aside
        ref={panelRef}
        className="panel activity-inspector-panel context-drawer-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <div className="context-drawer-heading">
          <h2 id={titleId}>{title}</h2>
          <button ref={closeButtonRef} className="activity-drawer-close" type="button" onClick={onClose}>
            Đóng
          </button>
        </div>
        {children}
      </aside>
    </div>
  );
};
