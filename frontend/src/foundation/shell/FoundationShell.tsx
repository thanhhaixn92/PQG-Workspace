import React from 'react';

export interface FoundationShellProps extends React.PropsWithChildren {
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Stable root for PQG Workspace Foundation surfaces.
 *
 * Wave 1 deliberately keeps layout/bootstrap behaviour in AppLayout while this
 * root establishes a durable shell boundary for later extraction of navigation,
 * ModuleCanvas and AgentDock. It must stay presentation-only.
 */
export function FoundationShell({ className = '', children, style }: FoundationShellProps) {
  return (
    <div
      className={`app-layout foundation-shell ${className}`.trim()}
      data-foundation-shell="true"
      style={style}
    >
      {children}
    </div>
  );
}
