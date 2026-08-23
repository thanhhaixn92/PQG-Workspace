import React from 'react';

export function PageHeader({ eyebrow, title, description, icon, actions, id }: { eyebrow?: string; title: React.ReactNode; description?: React.ReactNode; icon?: React.ReactNode; actions?: React.ReactNode; id?: string }) {
  return <header className="assistant-header page-header"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1 id={id}>{icon}{title}</h1>{description && <p>{description}</p>}</div>{actions}</header>;
}
