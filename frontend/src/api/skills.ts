import { apiFetch } from './client';

export interface Skill {
  id: string;
  name: string;
  description: string | null;
  content: string;
  enabled: boolean;
  status: 'draft' | 'review_pending' | 'approved';
  version?: number;
  updated_at: number;
}

export interface SkillVersion {
  id: string;
  skill_id: string;
  version_number: number;
  name: string;
  description: string | null;
  content: string;
  status: Skill['status'];
  updated_at: number;
}

export async function fetchSkills(): Promise<Skill[]> {
  return await apiFetch('/api/skills');
}

export async function createSkill(skill: { name: string; description?: string; content: string; enabled?: boolean }): Promise<Skill> {
  return await apiFetch('/api/skills', {
    method: 'POST',
    body: JSON.stringify(skill),
  });
}

export async function updateSkill(id: string, skill: Partial<Skill>): Promise<Skill> {
  return await apiFetch(`/api/skills/${id}`, {
    method: 'PUT',
    body: JSON.stringify(skill),
  });
}

export async function changeSkillStatus(id: string, status: Skill['status']): Promise<Skill> {
  return await apiFetch(`/api/skills/${id}/status`, {
    method: 'POST',
    body: JSON.stringify({ status }),
  });
}

export async function fetchSkillVersions(id: string): Promise<SkillVersion[]> {
  return await apiFetch(`/api/skills/${id}/versions`);
}

export async function deleteSkill(id: string): Promise<void> {
  await apiFetch(`/api/skills/${id}`, {
    method: 'DELETE',
  });
}
