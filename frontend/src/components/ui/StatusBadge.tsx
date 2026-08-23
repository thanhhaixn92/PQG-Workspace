import React from 'react';

export function StatusBadge({ children, tone = 'neutral' }: React.PropsWithChildren<{ tone?: 'neutral' | 'success' | 'warning' | 'danger' }>) {
  return <span className={`runtime-pill ${tone}`}>{children}</span>;
}
