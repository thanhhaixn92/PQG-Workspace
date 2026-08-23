import { describe, expect, it } from 'vitest';
import {
  FOUNDATION_ROUTES,
  MODULE_DEFINITIONS,
  PATH_BY_SIDEBAR_TAB,
  SIDEBAR_TAB_BY_PATH,
  getPrimaryModuleDefinitions,
} from './registry';

describe('Foundation module registry', () => {
  it('keeps Home, Settings and global GYO as fixed Foundation routes', () => {
    expect(FOUNDATION_ROUTES.map(route => route.id)).toEqual(['home', 'global-assistant', 'settings']);
    expect(FOUNDATION_ROUTES.every(route => route.fixed)).toBe(true);
  });

  it('preserves the current route-to-tab compatibility map', () => {
    expect(SIDEBAR_TAB_BY_PATH['/']).toBe('overview');
    expect(SIDEBAR_TAB_BY_PATH['/work']).toBe('sessions');
    expect(SIDEBAR_TAB_BY_PATH['/knowledge']).toBe('skills');
    expect(SIDEBAR_TAB_BY_PATH['/review']).toBe('review');
    expect(SIDEBAR_TAB_BY_PATH['/reports']).toBe('reports');
    expect(SIDEBAR_TAB_BY_PATH['/settings']).toBe('settings');
    expect(PATH_BY_SIDEBAR_TAB['memory-hub']).toBe('/memory-hub');
    expect(PATH_BY_SIDEBAR_TAB.dirap).toBe('/knowledge/search');
  });

  it('does not treat fixed Foundation surfaces as optional Modules', () => {
    const moduleTabs = MODULE_DEFINITIONS.map(module => module.tab);
    expect(moduleTabs).not.toContain('overview');
    expect(moduleTabs).not.toContain('settings');
    expect(moduleTabs).not.toContain('hermes');
  });

  it('exposes only the existing primary first-party Modules in the primary projection', () => {
    expect(getPrimaryModuleDefinitions().map(module => module.tab)).toEqual(['sessions', 'skills', 'review', 'reports']);
  });
});
