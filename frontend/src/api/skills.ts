import { apiFetch } from './client';

export interface Skill {
  id: string;
  name: string;
  description: string | null;
  content: string;
  enabled: boolean;
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

export async function deleteSkill(id: string): Promise<void> {
  await apiFetch(`/api/skills/${id}`, {
    method: 'DELETE',
  });
}
