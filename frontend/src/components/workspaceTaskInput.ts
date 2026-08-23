export interface ParsedWorkspaceTaskInput {
  title: string;
  dueAt: number | null;
  estimateMinutes: number | null;
}

/**
 * Parses only the explicit Vietnamese shorthand shown by the task form.
 * It never treats probabilistic inference as a confirmed deadline.
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
