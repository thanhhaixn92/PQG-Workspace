import React from 'react';

export function EmptyState({ title, description, action }: { title: React.ReactNode; description?: React.ReactNode; action?: React.ReactNode }) {
  return <div className="empty-state"><div className="empty-state-title">{title}</div>{description && <div className="empty-state-text">{description}</div>}{action}</div>;
}
