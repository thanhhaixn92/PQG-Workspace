import type { Skill } from '../api/skills';

export const OPEN_WORK_CONVERSATIONS_EVENT = 'hermes:open-work-conversations';

export const filterAvailableSkills = (skills: Skill[]) => skills.filter(item => item.enabled && item.status === 'approved');
