import React from 'react';

export function ErrorState({ message, onRetry }: { message: React.ReactNode; onRetry?: () => void }) {
  return <div className="inline-error" role="alert"><span>{message}</span>{onRetry && <button type="button" className="btn-secondary compact-button" onClick={onRetry}>Thử lại</button>}</div>;
}
