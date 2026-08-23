import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useHermesStore } from '../store/store';
import { changeSkillStatus, fetchSkillVersions, fetchSkills, createSkill, updateSkill, deleteSkill } from '../api/skills';
import type { Skill, SkillVersion } from '../api/skills';

export const SkillsPanel: React.FC = () => {
  const skills = useHermesStore(state => state.skills);
  const setSkills = useHermesStore(state => state.setSkills);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [newSkillName, setNewSkillName] = useState('');
  const [newSkillDesc, setNewSkillDesc] = useState('');
  const [newSkillContent, setNewSkillContent] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [versionsBySkill, setVersionsBySkill] = useState<Record<string, SkillVersion[] | undefined>>({});

  const filteredSkills = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return skills;
    return skills.filter(skill =>
      [skill.name, skill.description || '', skill.content]
        .some(value => value.toLowerCase().includes(keyword)),
    );
  }, [skills, search]);

  const loadSkills = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      const data = await fetchSkills();
      setSkills(data);
    } catch {
      setError('Không tải được danh sách kỹ năng.');
    } finally {
      setLoading(false);
    }
  }, [setSkills]);

  useEffect(() => {
    void loadSkills();
  }, [loadSkills]);

  const handleCreate = async () => {
    if (!newSkillName.trim() || !newSkillContent.trim()) return;
    setLoading(true);
    try {
      setError(null);
      await createSkill({ name: newSkillName, description: newSkillDesc, content: newSkillContent });
      await loadSkills();
      setNewSkillName('');
      setNewSkillDesc('');
      setNewSkillContent('');
    } catch {
      setError('Không tạo được kỹ năng.');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (skill: Skill) => {
    if (skill.status !== 'approved') return;
    setBusyId(skill.id);
    try {
      setError(null);
      await updateSkill(skill.id, { enabled: !skill.enabled });
      await loadSkills();
    } catch {
      setError('Không cập nhật được trạng thái kỹ năng.');
    } finally {
      setBusyId(null);
    }
  };

  const handleStatus = async (skill: Skill, status: Skill['status']) => {
    if (busyId) return;
    setBusyId(skill.id);
    try {
      setError(null);
      await changeSkillStatus(skill.id, status);
      await loadSkills();
    } catch {
      setError('Không chuyển được trạng thái kỹ năng. Hãy tải lại và thử lại.');
    } finally {
      setBusyId(null);
    }
  };

  const toggleVersions = async (skill: Skill) => {
    if (versionsBySkill[skill.id]) {
      setVersionsBySkill(current => ({ ...current, [skill.id]: undefined }));
      return;
    }
    setBusyId(skill.id);
    try {
      const versions = await fetchSkillVersions(skill.id);
      setVersionsBySkill(current => ({ ...current, [skill.id]: versions }));
    } catch {
      setError('Không tải được lịch sử phiên bản kỹ năng.');
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (deletingId || !window.confirm('Xóa kỹ năng “' + name + '”? Không thể hoàn tác.')) return;
    setDeletingId(id);
    try {
      setError(null);
      await deleteSkill(id);
      await loadSkills();
    } catch {
      setError('Không xóa được kỹ năng.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="skills-panel" style={{ padding: '12px', display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <h3 style={{ margin: '0 0 12px 0' }}>Kỹ năng</h3>
      <input
        placeholder="Tìm kỹ năng..."
        value={search}
        onChange={e => setSearch(e.target.value)}
        className="hermes-input"
        style={{ marginBottom: '10px' }}
      />
      {error && <div className="form-error">{error}</div>}

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {filteredSkills.map(skill => (
          <div key={skill.id} data-review-source="skill" data-review-id={skill.id} tabIndex={-1} style={{ border: '1px solid var(--border-subtle)', padding: '8px', marginBottom: '8px', borderRadius: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
              <div>
                <strong>{skill.name}</strong>
                <div style={{ fontSize: '11px', color: skill.enabled ? 'var(--success-primary)' : 'var(--text-secondary)' }}>
                  {skill.status === 'approved' ? 'Đã duyệt' : skill.status === 'review_pending' ? 'Chờ duyệt' : 'Bản nháp'} · {skill.enabled ? 'Đang dùng' : 'Chưa dùng'} · v{skill.version}
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px' }}>
                  <input
                    type="checkbox"
                    checked={skill.enabled}
                    onChange={() => void handleToggle(skill)}
                    disabled={skill.status !== 'approved' || busyId === skill.id}
                    title="Bật/tắt kỹ năng"
                  />
                  Bật
                </label>
                <button onClick={() => void handleDelete(skill.id, skill.name)} disabled={deletingId !== null} style={{ color: 'var(--error)' }}>
                  {deletingId === skill.id ? 'Đang xóa...' : 'Xóa'}
                </button>
              </div>
            </div>
            {skill.description && <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{skill.description}</div>}
            {search.trim() && skill.content.toLowerCase().includes(search.trim().toLowerCase()) && (
              <div className="runtime-guidance">Khớp trong nội dung: {skill.content.slice(0, 140)}{skill.content.length > 140 ? '…' : ''}</div>
            )}
            <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
              {skill.status === 'draft' && <button className="btn-secondary" disabled={busyId !== null} onClick={() => void handleStatus(skill, 'review_pending')}>Gửi duyệt</button>}
              {skill.status === 'review_pending' && <button className="btn-primary" disabled={busyId !== null} onClick={() => void handleStatus(skill, 'approved')}>Duyệt kỹ năng</button>}
              {skill.status !== 'draft' && <button className="btn-secondary" disabled={busyId !== null} onClick={() => void handleStatus(skill, 'draft')}>Đưa về nháp</button>}
              <button className="btn-secondary" disabled={busyId !== null} onClick={() => void toggleVersions(skill)}>Lịch sử phiên bản</button>
            </div>
            {versionsBySkill[skill.id] && <div className="runtime-guidance" style={{ marginTop: 6 }}>
              {versionsBySkill[skill.id]!.map(version => <div key={version.id}>v{version.version_number} · {version.status} · {new Date(version.updated_at * 1000).toLocaleString('vi-VN')}</div>)}
            </div>}
          </div>
        ))}
        {skills.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-title">Chưa có kỹ năng</div>
            <div className="empty-state-text">Thêm hướng dẫn ngắn để định hình các yêu cầu sau.</div>
          </div>
        )}
        {skills.length > 0 && filteredSkills.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-title">Không có kết quả phù hợp</div>
            <div className="empty-state-text">Thử từ khóa khác hoặc tạo kỹ năng mới.</div>
          </div>
        )}
      </div>

      <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <input
          placeholder="Tên"
          value={newSkillName}
          onChange={e => setNewSkillName(e.target.value)}
          className="hermes-input"
        />
        <input
          placeholder="Mô tả (không bắt buộc)"
          value={newSkillDesc}
          onChange={e => setNewSkillDesc(e.target.value)}
          className="hermes-input"
        />
        <textarea
          placeholder="Nội dung/hướng dẫn kỹ năng"
          value={newSkillContent}
          onChange={e => setNewSkillContent(e.target.value)}
          className="hermes-input"
          style={{ minHeight: '60px' }}
        />
        <button onClick={() => void handleCreate()} disabled={loading} className="hermes-button">
          Thêm kỹ năng
        </button>
      </div>
    </div>
  );
};
