import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ArtifactList } from './ArtifactList';
import { ApprovalItem, type ReviewProjection } from './ApprovalItem';
import { PhaseCard } from './PhaseCard';

describe('extracted Work and Review components', () => {
  it('keeps phase status and reorder actions wired', () => {
    const onChange = vi.fn();
    const onMoveDown = vi.fn();
    render(<PhaseCard phase={{ id: 'p1', session_id: 'w1', title: 'Phân tích', sort_order: 0, status: 'not_started', source: 'user', created_at: 1, updated_at: 1, steps: [] }} index={0} count={2} onChange={onChange} onMoveUp={vi.fn()} onMoveDown={onMoveDown}><div>Bước con</div></PhaseCard>);
    fireEvent.change(screen.getByLabelText('Trạng thái giai đoạn Phân tích'), { target: { value: 'in_progress' } });
    fireEvent.click(screen.getByRole('button', { name: 'Đưa giai đoạn Phân tích xuống' }));
    expect(onChange).toHaveBeenCalledWith({ status: 'in_progress' });
    expect(onMoveDown).toHaveBeenCalledOnce();
    expect(screen.getByText('Bước con')).toBeDefined();
  });

  it('renders a managed artifact link without exposing a system path', () => {
    render(<ArtifactList baseUrl="http://127.0.0.1:8000" sessionId="work-1" artifacts={[{ id: 'a1', session_id: 'work-1', relative_path: 'outputs/report.md', kind: 'report_markdown', sha256: 'hash', size_bytes: 12, created_at: 1 }]} />);
    const link = screen.getByRole('link', { name: 'report.md' });
    expect(link.getAttribute('href')).toBe('http://127.0.0.1:8000/api/sessions/work-1/artifacts/a1/content');
    expect(screen.queryByText(/C:\\/)).toBeNull();
  });

  it('keeps approval decisions explicit and source-bound', () => {
    const item: ReviewProjection = { id: 'pkg-1', source: 'Trợ lý', title: 'Cập nhật Work', status: 'Chờ bạn duyệt', category: 'pending', scope: 'Công việc hiện tại', risk: 'Local', before: 'Chưa đổi', after: 'Sẽ đổi', rollback: 'Có thể hoàn tác', destination: 'hermes' };
    const onDecide = vi.fn();
    render(<ApprovalItem item={item} expanded={false} busy={false} onToggle={vi.fn()} onDecide={onDecide} onOpen={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Duyệt gói đề xuất' }));
    expect(onDecide).toHaveBeenCalledWith('approve');
  });
});
