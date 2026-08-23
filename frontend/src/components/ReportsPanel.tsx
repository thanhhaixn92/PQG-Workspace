import React, { useCallback, useEffect, useRef, useState } from 'react';
import { FileText, RefreshCw } from 'lucide-react';
import { createMarkdownReport, listArtifacts, type Artifact } from '../api/artifacts';
import { BASE_URL } from '../api/client';
import { useHermesStore } from '../store/store';
import { getWorkDashboard } from '../api/works';
import { MarkdownRenderer } from './MarkdownRenderer';
import { ArtifactList } from './ArtifactList';

const newKey = () => globalThis.crypto?.randomUUID?.() ?? `report-${Date.now()}-${Math.random().toString(16).slice(2)}`;
type ReportTemplate = 'progress' | 'handoff' | 'decision';
type ReportSource = 'plan' | 'conversations' | 'artifacts' | 'approvals';

const templateLabels: Record<ReportTemplate, string> = {
  progress: 'Báo cáo tiến độ',
  handoff: 'Bàn giao công việc',
  decision: 'Ghi nhận quyết định',
};

export const ReportsPanel: React.FC = () => {
  const sessionId = useHermesStore(state => state.activeSessionId);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [outputFormat, setOutputFormat] = useState<'markdown' | 'html'>('markdown');
  const [template, setTemplate] = useState<ReportTemplate>('progress');
  const [sources, setSources] = useState<ReportSource[]>(['plan', 'conversations', 'artifacts', 'approvals']);
  const [previewing, setPreviewing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creatingDraft, setCreatingDraft] = useState(false);
  const requestVersion = useRef(0);

  const load = useCallback(async () => {
    if (!sessionId) return;
    const version = ++requestVersion.current;
    setLoading(true);
    try {
      const items = await listArtifacts(sessionId);
      if (version === requestVersion.current) {
        setArtifacts(items);
        setError(null);
      }
    } catch {
      if (version === requestVersion.current) setError('Không tải được danh sách đầu ra.');
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    requestVersion.current += 1;
    setArtifacts([]);
    setError(null);
    setTitle('');
    setContent('');
    setOutputFormat('markdown');
    setTemplate('progress');
    setSources(['plan', 'conversations', 'artifacts', 'approvals']);
    setPreviewing(false);
    setSaving(false);
    void load();
  }, [load]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!sessionId || !title.trim() || !content.trim()) return;
    const targetSessionId = sessionId;
    setSaving(true);
    try {
      const result = await createMarkdownReport(targetSessionId, title.trim(), content, newKey(), outputFormat);
      if (useHermesStore.getState().activeSessionId !== targetSessionId) return;
      setArtifacts(current => [result, ...current.filter(item => item.id !== result.id)]);
      setTitle('');
      setContent('');
      setError(null);
    } catch {
      if (useHermesStore.getState().activeSessionId === targetSessionId) setError('Không tạo được báo cáo. Hãy kiểm tra lại nội dung hoặc thử lại.');
    } finally {
      if (useHermesStore.getState().activeSessionId === targetSessionId) setSaving(false);
    }
  };

  const createWorkDraft = async () => {
    if (!sessionId || creatingDraft) return;
    const targetSessionId = sessionId;
    setCreatingDraft(true);
    try {
      const work = await getWorkDashboard(targetSessionId);
      if (useHermesStore.getState().activeSessionId !== targetSessionId) return;
      const nextStep = work.next_step ? `- ${work.next_step.title} (${work.next_step.status})` : '- Chưa có bước tiếp theo.';
      const outputs = work.artifacts.length
        ? work.artifacts.map(item => `- ${item.relative_path}`).join('\n')
        : '- Chưa có đầu ra đã quản lý.';
      const selectedSections: string[] = [];
      if (sources.includes('plan')) selectedSections.push(
        `## Mục tiêu\n${work.work.goal || 'Chưa đặt mục tiêu.'}`,
        `## Tiến độ\n${work.work.progress_percent}% · ${work.work.work_status} · nguồn tính: ${work.progress_source || 'backend'}`,
        `## Việc tiếp theo\n${nextStep}`,
      );
      if (sources.includes('conversations')) selectedSections.push(`## Trao đổi liên quan\n${work.conversations.length ? work.conversations.map(item => `- ${item.title}`).join('\n') : '- Chưa có phiên trao đổi.'}`);
      if (sources.includes('artifacts')) selectedSections.push(`## Đầu ra\n${outputs}`);
      if (sources.includes('approvals')) selectedSections.push(`## Mục đang chờ duyệt\n${work.pending_approval_count}`);
      const outline = template === 'handoff'
        ? ['## Trạng thái bàn giao\nBổ sung tình trạng và lưu ý cho người tiếp nhận.', ...selectedSections, '## Rủi ro và việc còn lại\nBổ sung rủi ro hoặc blocker.']
        : template === 'decision'
          ? ['## Quyết định\nNêu quyết định cần ghi nhận.', '## Căn cứ\nBổ sung căn cứ và phương án đã cân nhắc.', ...selectedSections, '## Hệ quả và hoàn tác\nBổ sung tác động và cách hoàn tác.']
          : [...selectedSections, '## Nhận định\nBổ sung nhận định và phạm vi báo cáo trước khi tạo.'];
      const sourceLabels: Record<ReportSource, string> = { plan: 'kế hoạch và tiến độ', conversations: 'danh sách phiên trao đổi', artifacts: 'đầu ra đã quản lý', approvals: 'mục chờ duyệt' };
      setTitle(title || `${templateLabels[template]} · ${work.work.title}`);
      setContent([
        ...outline,
        `## Nguồn và phạm vi\n- Công việc: ${work.work.title}\n- Dữ liệu dùng: ${sources.length ? sources.map(item => sourceLabels[item]).join(', ') : 'Không chọn nguồn tự động'}\n- Tạo lúc: ${new Date().toISOString()}\n- Nội dung là bản nháp có thể chỉnh sửa trước khi xuất bản.`,
      ].join('\n\n'));
      setError(null);
    } catch {
      if (useHermesStore.getState().activeSessionId === targetSessionId) setError('Chưa tạo được nháp từ dữ liệu Công việc. Hãy thử lại.');
    } finally {
      if (useHermesStore.getState().activeSessionId === targetSessionId) setCreatingDraft(false);
    }
  };

  if (!sessionId) {
    return <div className="empty-state"><div className="empty-state-title">Chưa chọn Công việc</div><div className="empty-state-text">Chọn một Công việc để xem và tạo báo cáo đầu ra.</div></div>;
  }

  return (
    <div className="list-panel reports-panel">
      <div className="section-header">
        <div><h3><FileText size={18} /> Báo cáo</h3><p>Tạo báo cáo Markdown hoặc HTML có thể mở và in thành PDF từ trình duyệt.</p></div>
        <div className="report-actions"><button className="btn-secondary compact-button" onClick={() => void createWorkDraft()} disabled={creatingDraft}>{creatingDraft ? 'Đang tạo nháp…' : 'Tạo nháp từ Công việc'}</button><button className="icon-button" title="Làm mới báo cáo" onClick={() => void load()} disabled={loading}><RefreshCw size={16} className={loading ? 'spin' : ''} /></button></div>
      </div>
      <div className="panel-content">
        <form className="session-form" onSubmit={submit}>
          <label>Mẫu báo cáo
            <select value={template} onChange={event => setTemplate(event.target.value as ReportTemplate)} aria-label="Mẫu báo cáo">
              {Object.entries(templateLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <fieldset className="report-source-options"><legend>Nguồn đưa vào bản nháp</legend>{(['plan', 'conversations', 'artifacts', 'approvals'] as ReportSource[]).map(source => <label key={source}><input type="checkbox" checked={sources.includes(source)} onChange={event => setSources(current => event.target.checked ? [...current, source] : current.filter(item => item !== source))} />{{ plan: 'Kế hoạch', conversations: 'Trao đổi', artifacts: 'Đầu ra', approvals: 'Mục chờ duyệt' }[source]}</label>)}</fieldset>
          <input value={title} onChange={event => setTitle(event.target.value)} placeholder="Tiêu đề báo cáo" aria-label="Tiêu đề báo cáo" />
          <textarea value={content} onChange={event => setContent(event.target.value)} placeholder="Nội dung báo cáo" aria-label="Nội dung báo cáo" rows={5} />
          <label>Định dạng
            <select value={outputFormat} onChange={event => setOutputFormat(event.target.value as 'markdown' | 'html')} aria-label="Định dạng báo cáo">
              <option value="markdown">Markdown</option>
              <option value="html">HTML để xem/in PDF</option>
            </select>
          </label>
          <button className="btn-secondary" type="button" onClick={() => setPreviewing(current => !current)} disabled={!content.trim()}>{previewing ? 'Đóng xem trước' : 'Xem trước báo cáo'}</button>
          <button className="btn-primary" disabled={saving || !title.trim() || !content.trim()}>{saving ? 'Đang tạo…' : `Tạo báo cáo ${outputFormat === 'html' ? 'HTML' : 'Markdown'}`}</button>
        </form>
        {previewing && <section className="report-preview" aria-label="Xem trước báo cáo"><h4>{title || 'Báo cáo chưa đặt tên'}</h4><MarkdownRenderer content={content} /></section>}
        {error && <div className="inline-error">{error}</div>}
        {loading && <div className="loading-indicator">Đang tải đầu ra…</div>}
        {!loading && artifacts.length === 0 && <div className="empty-state">Chưa có đầu ra được quản lý cho Công việc này.</div>}
        <ArtifactList artifacts={artifacts} sessionId={sessionId} baseUrl={BASE_URL} />
      </div>
    </div>
  );
};
