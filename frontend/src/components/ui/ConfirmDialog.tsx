import React, { useEffect, useRef } from 'react';

export function ConfirmDialog({ open, title, description, confirmLabel = 'Xác nhận', cancelLabel = 'Hủy', onConfirm, onCancel }: { open: boolean; title: string; description?: React.ReactNode; confirmLabel?: string; cancelLabel?: string; onConfirm: () => void; onCancel: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return <dialog ref={dialogRef} className="confirm-dialog" onCancel={event => { event.preventDefault(); onCancel(); }} onClose={() => { if (open) onCancel(); }}><h2>{title}</h2>{description && <div>{description}</div>}<div className="review-decision-actions"><button type="button" className="btn-primary" onClick={onConfirm}>{confirmLabel}</button><button type="button" className="btn-secondary" onClick={onCancel}>{cancelLabel}</button></div></dialog>;
}
