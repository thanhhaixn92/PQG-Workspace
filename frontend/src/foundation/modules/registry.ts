import type { SidebarTab } from '../../store/store';

export type FoundationSurfaceId = 'home' | 'global-assistant' | 'settings';
export type ModuleId = 'work' | 'documents' | 'knowledge' | 'memory' | 'memory-hub' | 'reports' | 'local-data' | 'research' | 'review';

export interface FoundationRouteDefinition {
  id: FoundationSurfaceId;
  tab: Extract<SidebarTab, 'overview' | 'hermes' | 'settings'>;
  path: string;
  fixed: true;
}

export interface ModuleDefinition {
  id: ModuleId;
  tab: Exclude<SidebarTab, 'overview' | 'hermes' | 'settings'>;
  defaultLabel: string;
  path: string;
  showInPrimaryNavigation: boolean;
  requiresWork: boolean;
}

export const FOUNDATION_ROUTES: readonly FoundationRouteDefinition[] = [
  { id: 'home', tab: 'overview', path: '/', fixed: true },
  { id: 'global-assistant', tab: 'hermes', path: '/assistant', fixed: true },
  { id: 'settings', tab: 'settings', path: '/settings', fixed: true },
] as const;

/**
 * First-party Module definitions for Wave 1.
 *
 * This registry is static and presentation-oriented. It does not represent
 * package installation, attachment persistence or permissions; those remain a
 * later protected gate.
 */
export const MODULE_DEFINITIONS: readonly ModuleDefinition[] = [
  { id: 'work', tab: 'sessions', defaultLabel: 'Công việc', path: '/work', showInPrimaryNavigation: true, requiresWork: false },
  { id: 'documents', tab: 'files', defaultLabel: 'Tài liệu', path: '/work/files', showInPrimaryNavigation: false, requiresWork: true },
  { id: 'knowledge', tab: 'skills', defaultLabel: 'Thư viện', path: '/knowledge', showInPrimaryNavigation: true, requiresWork: false },
  { id: 'review', tab: 'review', defaultLabel: 'Hộp duyệt', path: '/review', showInPrimaryNavigation: true, requiresWork: false },
  { id: 'reports', tab: 'reports', defaultLabel: 'Báo cáo', path: '/reports', showInPrimaryNavigation: true, requiresWork: false },
  { id: 'memory', tab: 'memory', defaultLabel: 'Bộ nhớ', path: '/memory', showInPrimaryNavigation: false, requiresWork: false },
  { id: 'memory-hub', tab: 'memory-hub', defaultLabel: 'Memory Hub', path: '/memory-hub', showInPrimaryNavigation: false, requiresWork: false },
  { id: 'local-data', tab: 'data', defaultLabel: 'Dữ liệu', path: '/data', showInPrimaryNavigation: false, requiresWork: false },
  { id: 'research', tab: 'dirap', defaultLabel: 'Nghiên cứu', path: '/knowledge/search', showInPrimaryNavigation: false, requiresWork: true },
] as const;

const allRouteDefinitions = [
  ...FOUNDATION_ROUTES,
  ...MODULE_DEFINITIONS,
] as const;

export const SIDEBAR_TAB_BY_PATH = Object.fromEntries(
  allRouteDefinitions.map(definition => [definition.path, definition.tab]),
) as Record<string, SidebarTab>;

export const PATH_BY_SIDEBAR_TAB = Object.fromEntries(
  allRouteDefinitions.map(definition => [definition.tab, definition.path]),
) as Record<SidebarTab, string>;

export function getModuleDefinitionByTab(tab: SidebarTab): ModuleDefinition | null {
  return MODULE_DEFINITIONS.find(definition => definition.tab === tab) ?? null;
}

export function getPrimaryModuleDefinitions(): readonly ModuleDefinition[] {
  return MODULE_DEFINITIONS.filter(definition => definition.showInPrimaryNavigation);
}
