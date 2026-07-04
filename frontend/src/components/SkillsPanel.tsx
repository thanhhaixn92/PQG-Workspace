import React, { useEffect, useMemo, useState } from 'react';
import { useHermesStore } from '../store/store';
import { fetchSkills, createSkill, updateSkill, deleteSkill } from '../api/skills';
import type { Skill } from '../api/skills';

export const SkillsPanel: React.FC = () => {
  const skills = useHermesStore(state => state.skills);
  const setSkills = useHermesStore(state => state.setSkills);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [newSkillName, setNewSkillName] = useState('');
  const [newSkillDesc, setNewSkillDesc] = useState('');
  const [newSkillContent, setNewSkillContent] = useState('');

  const filteredSkills = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return skills;
    return skills.filter(skill =>
      [skill.name, skill.description || '', skill.content]
        .some(value => value.toLowerCase().includes(keyword)),
    );
  }, [skills, search]);

  const loadSkills = async () => {
    try {
      setError(null);
      const data = await fetchSkills();
      setSkills(data);
    } catch {
      setError('Không tải được danh sách kỹ năng.');
    }
  };

  useEffect(() => {
    void loadSkills();
  }, []);

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
    try {
      setError(null);
      await updateSkill(skill.id, { enabled: !skill.enabled });
      await loadSkills();
    } catch {
      setError('Không cập nhật được trạng thái kỹ năng.');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      setError(null);
      await deleteSkill(id);
      await loadSkills();
    } catch {
      setError('Không xóa được kỹ năng.');
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
          <div key={skill.id} style={{ border: '1px solid var(--border-subtle)', padding: '8px', marginBottom: '8px', borderRadius: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
              <div>
                <strong>{skill.name}</strong>
                <div style={{ fontSize: '11px', color: skill.enabled ? 'var(--success-primary)' : 'var(--text-secondary)' }}>
                  {skill.enabled ? 'Đang bật' : 'Đang tắt'}
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px' }}>
                  <input
                    type="checkbox"
                    checked={skill.enabled}
                    onChange={() => void handleToggle(skill)}
                    title="Bật/tắt kỹ năng"
                  />
                  Bật
                </label>
                <button onClick={() => void handleDelete(skill.id)} style={{ color: 'var(--error)' }}>Xóa</button>
              </div>
            </div>
            {skill.description && <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{skill.description}</div>}
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
