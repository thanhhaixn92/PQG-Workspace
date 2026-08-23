import React, { useEffect, useState } from 'react';
import { CheckCircle2, Clock3, FileOutput, ShieldCheck } from 'lucide-react';
import { getOverview, type Overview } from '../api/overview';
import { useHermesStore } from '../store/store';
import { isTestWork } from './SessionList';
import { PRODUCT_NAME } from '../branding';

const dateLabel = (timestamp: number | null) => timestamp
  ? new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(timestamp * 1000)
  : 'Chưa có';

export const OverviewPanel: React.FC = () => {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const setActiveTab = useHermesStore(state => state.setSidebarTab);
  const setActiveSession = useHermesStore(state => state.setActiveSession);
  const visibleRecentWork = overview?.recent_work.filter(work => !isTestWork(work)) ?? [];

  useEffect(() => {
    let active = true;
    void getOverview()
      .then(data => { if (active) { setOverview(data); setError(null); } })
      .catch(() => {
        if (active) setError('Chưa tải được phần tổng quan. Bạn vẫn có thể tiếp tục làm việc từ mục Công việc.');
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const openWork = (id: string) => {
    setActiveSession(id);
    setActiveTab('sessions');
  };

  return (
    <main className="overview-panel" aria-labelledby="overview-title">
      <header className="overview-hero">
        <p className="eyebrow">{PRODUCT_NAME}</p>
        <h1 id="overview-title">Trợ lý công việc cá nhân chạy trên máy của bạn</h1>
        <p>Tạo một Công việc, trao đổi với trợ lý, quản lý tài liệu và lưu các đầu ra quan trọng ở cùng một nơi.</p>
        <button className="btn-primary" onClick={() => setActiveTab('sessions')}>Tạo hoặc mở Công việc</button>
      </header>

      {error && <div className="inline-error" role="status">{error}</div>}
      {loading && <div className="loading-indicator">Đang chuẩn bị tổng quan…</div>}
      {!loading && overview && <>
        <section className="overview-metrics" aria-label="Tình hình hiện tại">
          <div className="overview-metric"><Clock3 size={20} /><strong>{overview.active_work_count}</strong><span>việc đang xử lý</span></div>
          <div className="overview-metric"><ShieldCheck size={20} /><strong>{overview.pending_approval_count}</strong><span>mục chờ bạn duyệt</span></div>
          <div className="overview-metric"><FileOutput size={20} /><strong>{overview.output_count}</strong><span>đầu ra đã quản lý</span></div>
          <div className="overview-metric"><CheckCircle2 size={20} /><strong>{dateLabel(overview.latest_backup_at)}</strong><span>backup dữ liệu gần nhất</span></div>
        </section>
        <section className="overview-section" aria-labelledby="recent-work-title">
          <div><h2 id="recent-work-title">Công việc gần đây</h2><p>Chọn một Công việc để tiếp tục từ nơi bạn đã dừng.</p></div>
          {visibleRecentWork.length === 0 ? <div className="empty-state">Chưa có Công việc nào. Hãy tạo Công việc đầu tiên và nêu mục tiêu bạn muốn hoàn thành.</div> :
            <div className="overview-work-list">{visibleRecentWork.map(work => <button className="overview-work-item" key={work.id} onClick={() => openWork(work.id)}><span><strong>{work.title}</strong><small>{work.goal || 'Chưa đặt mục tiêu — bạn có thể bổ sung khi cần.'}</small></span><time>{dateLabel(work.last_opened_at || work.updated_at || null)}</time></button>)}</div>}
        </section>
        <section className="overview-section overview-next-step"><h2>Bắt đầu như thế nào?</h2><ol><li>Tạo một <strong>Công việc</strong> và ghi mục tiêu.</li><li>Mở Công việc, rồi chọn tab <strong>Trao đổi</strong> để giao yêu cầu cho GYO.</li><li>Trong cùng Công việc, dùng tab <strong>Tài liệu</strong> để quản lý nguồn và <strong>Đầu ra &amp; Báo cáo</strong> để xem kết quả.</li></ol></section>
      </>}
    </main>
  );
};
