import React from 'react';
import { FoundationShell } from '../../foundation/shell/FoundationShell';

/**
 * Compatibility wrapper retained for existing AppLayout imports.
 * New Foundation code should target FoundationShell directly.
 */
export function AppShell({ className = '', children, style }: React.PropsWithChildren<{ className?: string; style?: React.CSSProperties }>) {
  return <FoundationShell className={className} style={style}>{children}</FoundationShell>;
}
