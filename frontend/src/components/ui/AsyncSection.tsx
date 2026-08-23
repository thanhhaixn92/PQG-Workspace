import React from 'react';
import { EmptyState } from './EmptyState';
import { ErrorState } from './ErrorState';

export function AsyncSection({ loading, error, empty, emptyTitle = 'Chưa có dữ liệu', onRetry, children }: React.PropsWithChildren<{ loading?: boolean; error?: string | null; empty?: boolean; emptyTitle?: string; onRetry?: () => void }>) {
  if (loading) return <div className="loading-indicator" role="status">Đang tải…</div>;
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (empty) return <EmptyState title={emptyTitle} />;
  return <>{children}</>;
}
