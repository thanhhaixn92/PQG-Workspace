import React, { useEffect, useState } from 'react';
import { Clock3, FileText, ListChecks, Settings2 } from 'lucide-react';
import { useHermesStore } from '../store/store';
import { getWorkDashboard, type WorkDashboard } from '../api/works';
import { ActivityInspector } from './ActivityInspector';
import { OPEN_WORK_CONVERSATIONS_EVENT } from './WorkHub';

type DrawerTab = 'history' | 'context' | 'system';

const formatDate = (value?: number | null) => value
  ? new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short' }).format(value * 1000)
  : 'Chưa có';

export const WorkContextDrawer: React.FC = () => {
  const workId = useHermesStore(state => state.activeSessionId);
  const [tab, setTab] = useState<DrawerTab>('history');
  const [data, setData] = useState<WorkDashboard | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    if (!workId) {
      setData(null);
      return () => { active = false; };
    }
    void getWorkDashboard(workId)
      .then(value => { if (active) { setData(value); setError(false); } })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [workId]);

  return <div className="panel-content work-context-drawer">
      {!workId && <div className="empty-state">Chọn một Công việc để xem lịch sử và ngữ cảnh.</div>}
      {workId && <>
        <div className="activity-view-toggle" role="tablist" aria-label="Lịch sử và ngữ cảnh">
          <button className={tab === 'history' ? 'active' : ''} onClick={() => setTab('history')}>Lịch sử trao đổi</button>
          <button className={tab === 'context' ? 'active' : ''} onClick={() => setTab('context')}>Tóm tắt ngữ cảnh</button>
          <button className={tab === 'system' ? 'active' : ''} onClick={() => setTab('system')}>Hệ thống</button>
        </div>
        {error && <div className="inline-error">Chưa tải được thông tin Công việc.</div>}
        {tab === 'history' && <section className="drawer-history">
          <p>Những phiên trao đổi thuộc Công việc hiện tại.</p>
          {data?.conversations.map(item => <div className="drawer-conversation" key={item.id}>
            <Clock3 size={15} />
            <div><strong>{item.title}</strong><span>{item.purpose || `${item.message_count} tin nhắn`}</span></div>
            <time>{formatDate(item.updated_at)}</time>
          </div>)}
          {data && data.conversations.length === 0 && <div className="empty-state">Chưa có phiên trao đổi.</div>}
        </section>}
        {tab === 'context' && <section className="drawer-context">
          {data?.context_summary ? <>
            <h4>Tóm tắt phiên bản {data.context_summary.version}</h4>
            <p>{data.context_summary.content}</p>
            <small>Cập nhật {formatDate(data.context_summary.created_at)}. Phạm vi tin nhắn được ghi nhận cùng bản tóm tắt.</small>
          </> : <>
            <h4>Chưa có tóm tắt ngữ cảnh</h4>
            <p>Hermes chưa tạo tóm tắt cho Công việc này. Nội dung chat không tự động được đưa vào ngữ cảnh ngầm.</p>
            <button className="btn-secondary compact-button" onClick={() => window.dispatchEvent(new Event(OPEN_WORK_CONVERSATIONS_EVENT))}>Mở Trao đổi để yêu cầu Hermes tóm tắt</button>
            {data?.next_step && <div className="context-fact"><ListChecks size={16} /><span>Việc đang tiếp theo: {data.next_step.title}</span></div>}
            {data?.artifacts.slice(0, 3).map(item => <div className="context-fact" key={item.id}><FileText size={16} /><span>{item.relative_path}</span></div>)}
          </>}
        </section>}
        {tab === 'system' && <section className="drawer-system"><div className="runtime-guidance"><Settings2 size={15} /> Thông tin này dành cho người cần chẩn đoán. Nội dung nhạy cảm được che.</div><ActivityInspector /></section>}
      </>}
    </div>;
};
