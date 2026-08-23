import type { ReactNode } from 'react';
import { ChevronDown, ChevronUp, Pencil } from 'lucide-react';
import type { WorkPlanPhase } from '../api/works';

export function PhaseCard({ phase, index, count, onChange, onMoveUp, onMoveDown, children }: {
  phase: WorkPlanPhase;
  index: number;
  count: number;
  onChange: (updates: Partial<Pick<WorkPlanPhase, 'title' | 'status' | 'sort_order'>>) => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  children: ReactNode;
}) {
  return <article className="plan-phase">
    <div className="plan-phase-heading">
      <span>{index + 1}</span>
      <div>
        <h3>{phase.title}</h3>
        <select aria-label={`Trạng thái giai đoạn ${phase.title}`} value={phase.status} onChange={event => onChange({ status: event.target.value as WorkPlanPhase['status'] })}>
          <option value="not_started">Chưa bắt đầu</option><option value="in_progress">Đang làm</option><option value="blocked">Cần xử lý</option><option value="completed">Đã xong</option>
        </select>
      </div>
      <div>
        <button className="icon-button" type="button" aria-label={`Đưa giai đoạn ${phase.title} lên`} disabled={index === 0} onClick={onMoveUp}><ChevronUp size={16} /></button>
        <button className="icon-button" type="button" aria-label={`Đưa giai đoạn ${phase.title} xuống`} disabled={index === count - 1} onClick={onMoveDown}><ChevronDown size={16} /></button>
        <button className="icon-button" type="button" aria-label={`Đổi tên giai đoạn ${phase.title}`} onClick={() => { const title = window.prompt('Tên giai đoạn', phase.title); if (title?.trim()) onChange({ title: title.trim() }); }}><Pencil size={15} /></button>
      </div>
    </div>
    {children}
  </article>;
}
