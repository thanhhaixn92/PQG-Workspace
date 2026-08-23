import React from 'react';

export function MetricCard({ value, label, icon, onClick }: { value: React.ReactNode; label: React.ReactNode; icon?: React.ReactNode; onClick?: () => void }) {
  const content = <>{icon}<strong>{value}</strong><span>{label}</span></>;
  return onClick ? <button type="button" onClick={onClick}>{content}</button> : <div className="metric-card">{content}</div>;
}
