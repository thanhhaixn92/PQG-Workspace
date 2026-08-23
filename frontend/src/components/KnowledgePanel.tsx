import React, { useCallback, useEffect, useState } from 'react';
import { useHermesStore } from '../store/store';
import { SkillsPanel } from './SkillsPanel';
import { MemoryPanel } from './MemoryPanel';
import { MemoryHubPanel } from './MemoryHubPanel';
import { DirapPanel } from './DirapPanel';
import { ContextPreviewPanel } from './ContextPreviewPanel';
import { fetchGlobalMemory, fetchSessionMemory, type MemoryEntry } from '../api/memory';
import { fetchSkills, type Skill } from '../api/skills';
import { getAssistantContextManifest, type AssistantContextManifest } from '../api/assistant';
import { getKnowledgeSummary, type KnowledgeSummary } from '../api/knowledgeSummary';
import { useReviewTarget } from '../hooks/useReviewTarget';

type KnowledgeSection = 'overview' | 'context' | 'skills' | 'memory' | 'dirap' | 'advanced';

const LoadingSummary = () => <div className="knowledge-summary-loading">Đang đọc trạng thái Tri thức…</div>;

export const KnowledgePanel: React.FC = () => {
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const sessions = useHermesStore(state => state.sessions);
  const [section, setSection] = useState<KnowledgeSection>('overview');
  const [skills, setSkills] = useState<Skill[] | null>(null);
  const [memory, setMemory] = useState<MemoryEntry[] | null>(null);
  const [manifest, setManifest] = useState<AssistantContextManifest | null>(null);
  const [summary, setSummary] = useState<KnowledgeSummary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const selectReviewSource = useCallback((source: string) => {
    if (source === 'skill') setSection('skills');
    else if (source === 'knowledge') setSection('dirap');
    else if (source === 'memory_hub') setSection('advanced');
  }, []);
  useReviewTarget(selectReviewSource);

  useEffect(() => {
    let active = true;
    setSummaryError(null);
    setMemory(null);
    setSummary(null);
    Promise.allSettled([
      fetchSkills(),
      activeSessionId ? fetchSessionMemory(activeSessionId) : fetchGlobalMemory(),
      getAssistantContextManifest(activeSessionId),
      getKnowledgeSummary(activeSessionId),
    ]).then(results => {
      if (!active) return;
      if (results[0].status === 'fulfilled') setSkills(results[0].value);
      if (results[1].status === 'fulfilled') setMemory(results[1].value);
      if (results[2].status === 'fulfilled') setManifest(results[2].value);
      if (results[3].status === 'fulfilled') setSummary(results[3].value);
      if (results.some(result => result.status === 'rejected')) setSummaryError('Một số trạng thái Tri thức chưa tải được. Bạn vẫn có thể mở từng khu vực để thử lại.');
    });
    return () => { active = false; };
  }, [activeSessionId]);

  const activeWork = sessions.find(item => item.id === activeSessionId);
  const approvedSkillCount = skills?.filter(skill => skill.status === 'approved' && skill.enabled).length;
  return <div className="grouped-panel">
    <div className="grouped-panel-tabs" aria-label="Các nguồn tri thức">
      <button className={section === 'overview' ? 'active' : ''} onClick={() => setSection('overview')}>Tổng quan</button>
      <button className={section === 'context' ? 'active' : ''} onClick={() => setSection('context')} disabled={!activeSessionId}>Ngữ cảnh chat</button>
      <button className={section === 'skills' ? 'active' : ''} onClick={() => setSection('skills')}>Kỹ năng</button>
      <button className={section === 'memory' ? 'active' : ''} onClick={() => setSection('memory')}>Bộ nhớ dùng trong chat</button>
      <button className={section === 'dirap' ? 'active' : ''} onClick={() => setSection('dirap')} disabled={!activeSessionId}>Duyệt tri thức</button>
      <button className={section === 'advanced' ? 'active' : ''} onClick={() => setSection('advanced')}>Nâng cao</button>
    </div>
    <div className="grouped-panel-body">
      {section === 'overview' && <section className="knowledge-overview" aria-labelledby="knowledge-overview-title">
        <header><div><p className="eyebrow">Thư viện tri thức</p><h1 id="knowledge-overview-title">Tri thức dùng lại cho Trợ lý GYO</h1><p>Quản lý kỹ năng, bộ nhớ và tri thức có bằng chứng. Chỉ những mục được cho phép mới có thể xuất hiện trong ngữ cảnh chat.</p></div></header>
        {summaryError && <div className="inline-error" role="status">{summaryError}</div>}
        {!skills || !memory ? <LoadingSummary /> : <div className="knowledge-summary-grid">
          <button onClick={() => setSection('skills')}><strong>{approvedSkillCount ?? 0}</strong><span>Kỹ năng đang được phép dùng</span><small>Nháp và mục chờ duyệt không được đưa vào chat.</small></button>
          <button onClick={() => setSection('memory')}><strong>{memory.length}</strong><span>Bộ nhớ {activeWork ? 'của Công việc này' : 'toàn cục'}</span><small>{activeWork ? activeWork.title : 'Chọn Công việc để xem bộ nhớ theo phạm vi.'}</small></button>
          <button onClick={() => activeSessionId && setSection('context')} disabled={!activeSessionId}><strong>{summary?.context_included_count ?? manifest?.included.length ?? 0}</strong><span>Mục trong ngữ cảnh hiện tại</span><small>{activeSessionId ? `${summary?.context_excluded_count ?? manifest?.excluded.length ?? 0} mục bị loại — mở để xem lý do.` : 'Chọn Công việc để xem ngữ cảnh.'}</small></button>
          <button onClick={() => setSection('overview')}><strong>{summary?.pending_review_count ?? 0}</strong><span>Mục đang chờ rà soát</span><small>Hộp duyệt chỉ tổng hợp; quyết định vẫn diễn ra tại đúng nguồn.</small></button>
          <button onClick={() => setSection('advanced')}><strong>Memory Hub</strong><span>Tri thức nâng cao theo phạm vi</span><small>Không tự động được đưa vào chat.</small></button>
        </div>}
        <div className="knowledge-next-step"><strong>Bạn muốn bắt đầu từ đâu?</strong><div><button className="btn-primary" onClick={() => setSection('skills')}>Quản lý kỹ năng</button><button className="btn-secondary" onClick={() => setSection('memory')}>Xem bộ nhớ</button>{activeSessionId && <button className="btn-secondary" onClick={() => setSection('dirap')}>Duyệt tri thức tài liệu</button>}</div></div>
      </section>}
      {section === 'context' && <ContextPreviewPanel />}
      {section === 'skills' && <SkillsPanel />}
      {section === 'memory' && <MemoryPanel />}
      {section === 'dirap' && activeSessionId && <DirapPanel />}
      {section === 'dirap' && !activeSessionId && <div className="empty-state">Chọn một Công việc trước khi duyệt tri thức từ tài liệu.</div>}
      {section === 'advanced' && <><div className="runtime-guidance knowledge-boundary">Memory Hub là kho tri thức nâng cao theo phạm vi Công việc. Nội dung tại đây chưa tự động được đưa vào chat.</div><MemoryHubPanel currentWorkId={activeSessionId} /></>}
    </div>
  </div>;
};
