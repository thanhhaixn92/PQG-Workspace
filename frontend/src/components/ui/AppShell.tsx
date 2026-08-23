import React from 'react';

export function AppShell({ className = '', children, style }: React.PropsWithChildren<{ className?: string; style?: React.CSSProperties }>) {
  return <div className={`app-layout ${className}`.trim()} style={style}>{children}</div>;
}
