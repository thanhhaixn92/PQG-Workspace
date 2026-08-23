import React, { useEffect } from 'react';
import { FoundationShell } from '../../foundation/shell/FoundationShell';
import { useModuleProjectionStore } from '../../foundation/modules/store';

/**
 * Compatibility wrapper retained for existing AppLayout imports.
 * New Foundation code should target FoundationShell directly.
 */
export function AppShell({ className = '', children, style }: React.PropsWithChildren<{ className?: string; style?: React.CSSProperties }>) {
  const moduleProjectionStatus = useModuleProjectionStore(state => state.status);
  const refreshModules = useModuleProjectionStore(state => state.refresh);

  useEffect(() => {
    if (moduleProjectionStatus === 'idle') void refreshModules();
  }, [moduleProjectionStatus, refreshModules]);

  return <FoundationShell className={className} style={style}>{children}</FoundationShell>;
}
