import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Bot, CalendarClock, CheckCircle2, CircleAlert, ClipboardList, Play, Plus, RefreshCw, Sparkles, X } from 'lucide-react';
import { useHermesStore } from '../store/store';
import { getWorkspaceTabFromLocation, navigateToGyoAssistant, navigateToWorkspaceTab, type WorkspaceRouteTab } from '../navigation';
import { createSession } from '../api/sessions';
import { WorkHub } from './WorkHub';
import { isTestWork } from './SessionList';
import {
  createWorkspaceAiJob, createWorkspaceTask, deleteWorkspaceTask, getWorkspaceAiJobs, getWorkspaceHistory, getWorkspaceToday, getWorkspaceUpcoming, updateWorkspaceTask,
  type WorkspaceAiJob, type WorkspaceDashboard, type WorkspaceTask,
} from '../api/workspace';

type WorkspaceTab = WorkspaceRouteTab;

const formatDate = (value?: number | null) => value ? new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(value * 1000) : 'Chưa đặt hạn';
const statusLabel: Record<WorkspaceTask['status'], string> = { planned: 'Đã lên kế hoạch', ready: 'Sẵn sàng', in_progress: 'Đang làm', blocked: 'Đang bị chặn', waiting: 'Đang chờ', done: 'Hoàn tất', cancelled: 'Đã hủy' };
const aiJobStatusLabel: Record<WorkspaceAiJob['status'], string> = { queued: 'Đang xếp hàng', running: 'GYO đang xử lý', waiting_user: 'Chờ bạn gửi yêu cầu cho GYO', completed: 'Đã hoàn tất', failed: 'Không hoàn tất', cancelled: 'Đã hủy' };

export interface ParsedWorkspaceTaskInput {
  title: string;
  dueAt: number | null;
  estimateMinutes: number | null;
}

/**
 * Small, explicit Vietnamese parser for the create form. It recognises only
 * the unambiguous local shorthand we show in the UI; it never presents a
 * probabilistic model inference as a confirmed deadline.
 */
export const parseWorkspaceTaskInput = (value: string, now = new Date()): ParsedWorkspaceTaskInput => {
  const source = value.trim().replace(/\s+/g, ' ');
  const timeFirst = /(?:lúc\s*|vào\s*)?(\d{1,2})(?::(\d{2}))?\s*(?:ngày\s*)?mai\b/i.exec(source);
  const dateFirst = /(?:ngày\s*)?mai\s*(?:lúc|vào)?\s*(\d{1,2})(?::(\d{2}))?\b/i.exec(source);
  const time = timeFirst ?? dateFirst;
  let dueAt: number | null = null;
  if (time) {
    const hours = Number(time[1]);
    const minutes = Number(time[2] ?? 0);
    if (hours < 24 && minutes < 60) {
      const due = new Date(now);
      due.setDate(due.getDate() + 1);
      due.setHours(hours, minutes, 0, 0);
      dueAt = Math.floor(due.getTime() / 1000);
    }
  }

  const duration = /(?:khoảng|tầm|ước tính)?\s*(\d+(?:[.,]\d+)?)\s*(giờ|phút)/i.exec(source);
  let estimateMinutes: number | null = null;
  if (duration) {
    const amount = Number(duration[1].replace(',', '.'));
    estimateMinutes = Math.round(amount * (duration[2].toLowerCase() === 'giờ' ? 60 : 1));
    if (!Number.isFinite(estimateMinutes) || estimateMinutes < 1) estimateMinutes = null;
  }

  const title = source
    .replace(/\s*,?\s*(?:lúc\s*|vào\s*)?\d{1,2}(?::\d{2})?\s*(?:ngày\s*)?mai\b/gi, '')
    .replace(/\s*,?\s*(?:ngày\s*)?mai\s*(?:lúc|vào)?\s*\d{1,2}(?::\d{2})?\b/gi, '')
    .replace(/\s*,?\s*(?:khoảng|tầm|ước tính)?\s*\d+(?:[.,]\d+)?\s*(?:giờ|phút)/gi, '')
    .replace(/[\s,;]+$/g, '')
    .trim() || source;

  return { title, dueAt, estimateMinutes };
};

export const WorkWorkspace: React.FC = () => {
  const sessions = useHermesStore(state => state.sessions);
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const setActiveSession = useHermesStore(state => state.setActiveSession);
  const addSession = useHermesStore(state => state.addSession);
  const [tab, setTab] = useState<WorkspaceTab>(() => getWorkspaceTabFromLocation());
  const [today, setToday] = useState<WorkspaceDashboard | null>(null);
  const [tasks, setTasks] = useState<WorkspaceTask[]>([]);
  const [jobs, setJobs] = useState<WorkspaceAiJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [undoing, setUndoing] = useState(false);
  const [title, setTitle] = useState('');
  const [workId, setWorkId] = useState('');
  const [workTitle, setWorkTitle] = useState('');
  const [creatingWork, setCreatingWork] = useState(false);
  const [formOpen, setFormOpen] = useState(true);
  const [createdTask, setCreatedTask] = useState<WorkspaceTask | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const taskTitleRef = useRef<HTMLInputElement>(null);
  const workTitleRef = useRef<HTMLInputElement>(null);

  const visibleWorks = useMemo(() => sessions.filter(work => work.id !== 'test' && !isTestWork(work)), [sessions]);
  useEffect(() => {
    if (!workId && activeSessionId && visibleWorks.some(work => work.id === activeSessionId)) setWorkId(activeSessionId);
  }, [activeSessionId, visibleWorks, workId]);
  useEffect(() => {
    const syncWorkspaceTab = () => setTab(getWorkspaceTabFromLocation());
    window.addEventListener('popstate', syncWorkspaceTab);
    return () => window.removeEventListener('popstate', syncWorkspaceTab);
  }, []);
  const reload = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [nextToday, nextTasks, nextJobs] = await Promise.all([getWorkspaceToday(), tab === 'history' ? getWorkspaceHistory() : getWorkspaceUpcoming(), getWorkspaceAiJobs()]);
      setToday(nextToday); setTasks(nextTasks); setJobs(nextJobs);
    } catch { setError('Không tải được dữ liệu Công việc. Hãy kiểm tra backend rồi thử lại.'); }
    finally { setLoading(false); }
  }, [tab]);
  useEffect(() => { void reload(); }, [reload]);

  // The detail route remains a drawer: Escape and the backdrop close it,
  // while the selected Work and page scroll stay untouched underneath.
  useEffect(() => {
    if (!detailsOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setDetailsOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [detailsOpen]);

  const selectTask = (task: WorkspaceTask) => { setActiveSession(task.session_id); setDetailsOpen(true); };
  const startTask = async (task: WorkspaceTask) => { try { await updateWorkspaceTask(task.id, { status: 'in_progress', version: task.version }); await reload(); setActiveSession(task.session_id); setDetailsOpen(true); } catch { setError('Không thể bắt đầu việc. Hãy làm mới rồi thử lại.'); } };
  const delegate = async (task: WorkspaceTask) => {
    try {
      const job = await createWorkspaceAiJob(task.id, `workspace-ai-job-${crypto.randomUUID()}`);
      if (!job.conversation_id || !job.assistant_thread_id) {
        setError('GYO chưa trả về phiên làm việc hợp lệ. Hãy làm mới rồi thử lại.');
        return;
      }
      setActiveSession(task.session_id);
      navigateToGyoAssistant(task.session_id, job.conversation_id, job.assistant_thread_id);
      await reload();
    } catch { setError('Không thể giao việc cho GYO. Hãy làm mới rồi thử lại.'); }
  };
  const createTask = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim() || !workId) return;
    setCreating(true); setError(null);
    try {
      const parsed = parseWorkspaceTaskInput(title);
      const created = await createWorkspaceTask({
        session_id: workId, title: parsed.title, priority: 3, impact: 3, ai_eligibility: 'assistable',
        due_at: parsed.dueAt, estimate_minutes: parsed.estimateMinutes,
      }, crypto.randomUUID());
      setCreatedTask(created); setTitle(''); setWorkId(''); setFormOpen(false); await reload();
    } catch { setError('Không tạo được việc. Hãy thử lại.'); }
    finally { setCreating(false); }
  };
  const undoCreateTask = async () => {
    if (!createdTask || undoing) return;
    setUndoing(true); setError(null);
    try {
      await deleteWorkspaceTask(createdTask.id);
      setCreatedTask(null);
      await reload();
    } catch { setError('Không thể hoàn tác việc vừa tạo. Hãy thử lại.'); }
    finally { setUndoing(false); }
  };
  const createFirstWork = async (event: React.FormEvent) => {
    event.preventDefault();
    const nextWorkTitle = workTitle.trim();
    if (!nextWorkTitle || creatingWork) return;
    setCreatingWork(true); setError(null);
    try {
      const work = await createSession(nextWorkTitle);
      addSession(work);
      setActiveSession(work.id);
      setWorkId(work.id);
      setWorkTitle('');
      setFormOpen(true);
      window.requestAnimationFrame(() => taskTitleRef.current?.focus());
    } catch { setError('Không tạo được Công việc. Hãy kiểm tra backend rồi thử lại.'); }
    finally { setCreatingWork(false); }
  };
  const beginTaskCreation = () => {
    if (visibleWorks.length === 0) {
      window.requestAnimationFrame(() => workTitleRef.current?.focus());
      return;
    }
    if (activeSessionId && visibleWorks.some(work => work.id === activeSessionId)) setWorkId(activeSessionId);
    setFormOpen(true);
    window.requestAnimationFrame(() => taskTitleRef.current?.focus());
  };
  const parsedDraft = useMemo(() => parseWorkspaceTaskInput(title), [title]);

  const taskList = tab === 'today' ? today?.timeline ?? [] : tab === 'ai' ? [] : tasks;
  return <section className="work-workspace" aria-label="Không gian Công việc">
    <header className="work-workspace-header">
      <div><p>Không gian điều phối</p><span>Tập trung vào việc cần làm tiếp theo trên các công việc đang hoạt động.</span></div>
      <div className="work-workspace-header-actions"><button className="btn-secondary" type="button" onClick={beginTaskCreation}><Plus size={16} /> Tạo việc</button><button className="btn-secondary" type="button" onClick={() => void reload()} aria-label="Làm mới Công việc"><RefreshCw size={16} /> Làm mới</button></div>
    </header>
    <nav className="workspace-tabs" aria-label="Chế độ xem Công việc">
      {([['today', 'Hôm nay'], ['upcoming', 'Sắp tới'], ['ai', 'AI đang làm'], ['history', 'Lịch sử']] as const).map(([id, label]) => <button key={id} className={tab === id ? 'active' : ''} onClick={() => { navigateToWorkspaceTab(id); setTab(id); }}>{label}</button>)}
    </nav>
    {error && <div className="workspace-error" role="alert">{error}</div>}
    {loading ? <div className="empty-state">Đang tải Công việc…</div> : <>
      {tab === 'today' && <div className="workspace-today-grid">
        <article className={`workspace-recommendation ${today?.recommendation ? '' : 'is-empty'}`}>
          <div className="workspace-eyebrow"><Sparkles size={16} /> Việc nên làm ngay</div>
          {today?.recommendation ? <>
            <h2>{today.recommendation.title}</h2><p>{today.recommendation.description || 'Chưa có mô tả chi tiết.'}</p>
            <div className="workspace-meta"><span>{today.recommendation.work_title}</span><span><CalendarClock size={14} /> {formatDate(today.recommendation.due_at)}</span></div>
            <div className="workspace-reason"><strong>Vì sao việc này?</strong><span>{today.recommendation_reason}</span></div>
            <div className="workspace-actions"><button className="btn-primary" onClick={() => void startTask(today.recommendation!)}><Play size={16} /> Bắt đầu</button>{today.recommendation.ai_eligibility !== 'human_only' && <button className="btn-secondary" onClick={() => void delegate(today.recommendation!)}><Bot size={16} /> Giao GYO</button>}</div>
          </> : <><h2>{visibleWorks.length ? 'Chưa có việc nào cho hôm nay' : 'Chưa có Công việc nào'}</h2><p>{visibleWorks.length ? 'Tạo việc đầu tiên để Workspace đề xuất việc cần ưu tiên.' : 'Tạo một Công việc trước, sau đó thêm các việc cần thực hiện trong đó.'}</p><div className="workspace-actions"><button className="btn-primary" type="button" onClick={beginTaskCreation}><Plus size={16} /> {visibleWorks.length ? 'Tạo việc đầu tiên' : 'Tạo Công việc đầu tiên'}</button></div></>}
        </article>
        <aside className="workspace-attention"><h2><CircleAlert size={18} /> Cần chú ý</h2>{today?.attention_items.length ? today.attention_items.map(item => <button key={item.id} onClick={() => { const task = today.timeline.find(candidate => candidate.id === item.task_id); if (task) selectTask(task); }}><strong>{item.title}</strong><span>{item.detail}</span></button>) : <p>Không có việc bị chặn hoặc quá hạn.</p>}</aside>
        <section className="workspace-timeline"><h2><CalendarClock size={18} /> Lịch hôm nay</h2>{taskList.length ? taskList.map(task => <TaskRow key={task.id} task={task} onSelect={selectTask} />) : <p>Lịch sẽ xuất hiện khi có việc.</p>}</section>
        <section className="workspace-alternatives"><h2>Lựa chọn tiếp theo</h2>{today?.alternatives.length ? today.alternatives.map(task => <TaskRow key={task.id} task={task} onSelect={selectTask} />) : <p>Chưa có lựa chọn thay thế.</p>}</section>
      </div>}
      {tab === 'ai' && <section className="workspace-list-card"><h2><Bot size={18} /> AI đang làm</h2>{jobs.length ? jobs.map(job => <article key={job.id} className="workspace-job"><div><strong>{job.task_title}</strong><span>{job.work_title}</span></div><div><strong>{aiJobStatusLabel[job.status]}</strong><span>{job.stage_text || 'Đang chờ cập nhật'}</span></div></article>) : <p>GYO chưa có việc đang xử lý.</p>}</section>}
      {(tab === 'upcoming' || tab === 'history') && <section className="workspace-list-card"><h2>{tab === 'upcoming' ? 'Sắp tới' : 'Lịch sử'}</h2>{taskList.length ? taskList.map(task => <TaskRow key={task.id} task={task} onSelect={selectTask} />) : <p>{tab === 'history' ? 'Chưa có việc đã hoàn tất.' : 'Chưa có việc sắp tới.'}</p>}</section>}
    </>}
    {createdTask && <div className="workspace-create-success" role="status"><span>Đã tạo “{createdTask.title}”.</span><button className="btn-secondary compact-button" type="button" onClick={() => void undoCreateTask()} disabled={undoing}>{undoing ? 'Đang hoàn tác…' : 'Hoàn tác'}</button></div>}
    {visibleWorks.length === 0 ? <form className="workspace-create-work" onSubmit={createFirstWork}><div><strong>Tạo Công việc để bắt đầu</strong><span>Một việc luôn thuộc một Công việc; ứng dụng sẽ tự tạo nơi lưu trữ an toàn nếu bạn không chọn vị trí riêng.</span></div><input ref={workTitleRef} value={workTitle} onChange={event => setWorkTitle(event.target.value)} placeholder="Ví dụ: Kế hoạch tháng 9" aria-label="Tên Công việc mới" /><button className="btn-primary" disabled={creatingWork || !workTitle.trim()}><Plus size={16} /> {creatingWork ? 'Đang tạo…' : 'Tạo Công việc mới'}</button></form> : formOpen && <form className="workspace-create" onSubmit={createTask}><ClipboardList size={18} /><input ref={taskTitleRef} value={title} onChange={event => setTitle(event.target.value)} placeholder="Tạo việc mới…" aria-label="Tên việc mới" />{(parsedDraft.dueAt || parsedDraft.estimateMinutes) && <p className="workspace-create-hint" role="status">Nhận diện: {parsedDraft.dueAt ? `hạn ${formatDate(parsedDraft.dueAt)}` : ''}{parsedDraft.dueAt && parsedDraft.estimateMinutes ? ' · ' : ''}{parsedDraft.estimateMinutes ? `ước lượng ${parsedDraft.estimateMinutes >= 60 ? `${parsedDraft.estimateMinutes / 60} giờ` : `${parsedDraft.estimateMinutes} phút`}` : ''}.</p>}<select value={workId} onChange={event => setWorkId(event.target.value)} aria-label="Công việc của việc"><option value="">Chọn công việc</option>{visibleWorks.map(work => <option key={work.id} value={work.id}>{work.title}</option>)}</select><button className="btn-primary" disabled={creating || !title.trim() || !workId}><Plus size={16} /> Tạo việc</button></form>}
    {detailsOpen && <div className="workspace-detail-backdrop" role="presentation" onClick={event => { if (event.target === event.currentTarget) setDetailsOpen(false); }}><section className="workspace-detail-drawer" role="dialog" aria-modal="true" aria-label="Chi tiết Công việc"><button type="button" className="icon-button" onClick={() => setDetailsOpen(false)} aria-label="Đóng chi tiết"><X size={18} /></button><WorkHub /></section></div>}
  </section>;
};

const TaskRow: React.FC<{ task: WorkspaceTask; onSelect: (task: WorkspaceTask) => void }> = ({ task, onSelect }) => <button className="workspace-task-row" onClick={() => onSelect(task)} aria-label={`${task.title} · ${statusLabel[task.status]} · ${formatDate(task.due_at)}`}><span className={task.status === 'done' ? 'task-done' : ''}>{task.status === 'done' ? <CheckCircle2 size={17} /> : <ClipboardList size={17} />}</span><span><strong title={task.title}>{task.title}</strong><small>{task.work_title ? `Thuộc Công việc: ${task.work_title} · ` : ''}{statusLabel[task.status]}</small></span><small>{formatDate(task.due_at)}</small></button>;
