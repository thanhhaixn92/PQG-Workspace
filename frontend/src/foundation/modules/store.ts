import { create } from 'zustand';
import { getModuleInstances, type ModuleInstance } from '../../api/modules';

export type ModuleProjectionStatus = 'idle' | 'loading' | 'ready' | 'error';

interface ModuleProjectionStore {
  instances: ModuleInstance[];
  status: ModuleProjectionStatus;
  error: string | null;
  refresh: () => Promise<void>;
  setInstances: (instances: ModuleInstance[]) => void;
  replaceInstance: (instance: ModuleInstance) => void;
}

export const useModuleProjectionStore = create<ModuleProjectionStore>((set) => ({
  instances: [],
  status: 'idle',
  error: null,
  refresh: async () => {
    set({ status: 'loading', error: null });
    try {
      const instances = await getModuleInstances();
      set({ instances, status: 'ready', error: null });
    } catch {
      // Static registry remains the UI compatibility fallback. An unavailable
      // projection must not make Home/Settings/GYO fail to boot.
      set({ status: 'error', error: 'Chưa tải được trạng thái Modules.' });
    }
  },
  setInstances: (instances) => set({ instances, status: 'ready', error: null }),
  replaceInstance: (instance) => set((state) => ({
    instances: state.instances.map(item => item.module_id === instance.module_id ? instance : item),
    status: 'ready',
    error: null,
  })),
}));
