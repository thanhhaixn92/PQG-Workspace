import type { ComponentType } from 'react';

export type SurfaceLoader = () => Promise<{ default: ComponentType }>;

export interface ModuleCanvasLoaders {
  work: SurfaceLoader;
  fileExplorer: SurfaceLoader;
  editor: SurfaceLoader;
  knowledge: SurfaceLoader;
  reports: SurfaceLoader;
  review: SurfaceLoader;
  memory: SurfaceLoader;
  memoryHub: SurfaceLoader;
  localData: SurfaceLoader;
  research: SurfaceLoader;
}

export const DEFAULT_MODULE_CANVAS_LOADERS: ModuleCanvasLoaders = {
  work: () => import('../../components/WorkWorkspace').then(module => ({ default: module.WorkWorkspace })),
  fileExplorer: () => import('../../components/FileExplorer').then(module => ({ default: module.FileExplorer })),
  editor: () => import('./EditorSurface'),
  knowledge: () => import('../../components/KnowledgePanel').then(module => ({ default: module.KnowledgePanel })),
  reports: () => import('../../components/ReportsPanel').then(module => ({ default: module.ReportsPanel })),
  review: () => import('../../components/ReviewInboxPanel').then(module => ({ default: module.ReviewInboxPanel })),
  memory: () => import('../../components/MemoryPanel').then(module => ({ default: module.MemoryPanel })),
  memoryHub: () => import('../../components/MemoryHubPanel').then(module => ({ default: module.MemoryHubPanel })),
  localData: () => import('../../components/LocalDataPanel').then(module => ({ default: module.LocalDataPanel })),
  research: () => import('../../components/DirapPanel').then(module => ({ default: module.DirapPanel })),
};
