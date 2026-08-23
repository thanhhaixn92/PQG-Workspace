const TEST_WORK_MARKERS = ['uat-codex-', 'smoke test', '404test-', 'e2e', 'uat resolver', 'uat remediation summary', 'ki?m tra hermes oauth', 'memory hub mcp e2e'];

export function isTestWork(session: { title: string; workspace_path: string }): boolean {
  if (import.meta.env.VITE_SHOW_TEST_WORKS === '1') return false;
  const searchable = `${session.title} ${session.workspace_path}`.toLocaleLowerCase();
  return TEST_WORK_MARKERS.some(marker => searchable.includes(marker));
}
