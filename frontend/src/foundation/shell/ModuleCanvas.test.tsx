import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ModuleInstance } from '../../api/modules';
import { useHermesStore } from '../../store/store';
import { useModuleProjectionStore } from '../modules/store';
import { ModuleCanvas } from './ModuleCanvas';
import type { ModuleCanvasLoaders, SurfaceLoader } from './moduleCanvasLoaders';

type LoadedSurface = Awaited<ReturnType<SurfaceLoader>>;

vi.mock('../../components/AssistantChatSidebar', () => ({ AssistantChatSidebar: ({ surfaceMode }: { surfaceMode?: string }) => <div>GYO {surfaceMode ?? 'drawer'}</div> }));
vi.mock('../../components/OverviewPanel', () => ({ OverviewPanel: () => <div>Overview content</div> }));
vi.mock('../../components/SettingsPanel', () => ({ SettingsPanel: () => <div>Settings content</div> }));

const instanceFor = (moduleId: string, attached = true): ModuleInstance => ({
  id: `builtin:${moduleId}`,
  module_id: moduleId,
  source_kind: 'builtin',
  package_id: null,
  display_name: moduleId,
  attached,
  sort_order: 20,
  config: {},
  config_version: 1,
  health_state: 'ready',
  revision: 1,
  created_at: 1,
  updated_at: 1,
});

const unavailableProjectionStatuses = ['idle', 'loading', 'error'] as const;

const resolvedLoader = (label: string): ReturnType<typeof vi.fn<SurfaceLoader>> => vi.fn(async () => ({
  default: () => <div>{label}</div>,
}));

function deferredLoader() {
  let resolve!: (value: LoadedSurface) => void;
  const loader: SurfaceLoader = () => new Promise<LoadedSurface>(resolver => {
    resolve = resolver;
  });
  return { loader: vi.fn(loader), resolve: (value: LoadedSurface) => resolve(value) };
}

function makeLoaders(): ModuleCanvasLoaders {
  return {
    work: resolvedLoader('Work content'),
    fileExplorer: resolvedLoader('File explorer'),
    editor: resolvedLoader('Editor content'),
    knowledge: resolvedLoader('Knowledge content'),
    reports: resolvedLoader('Reports content'),
    review: resolvedLoader('Review content'),
    memory: resolvedLoader('Memory content'),
    memoryHub: resolvedLoader('Memory Hub content'),
    localData: resolvedLoader('Local data content'),
    research: resolvedLoader('Research content'),
  };
}

describe('ModuleCanvas', () => {
  let loaders: ModuleCanvasLoaders;

  beforeEach(() => {
    loaders = makeLoaders();
    useHermesStore.setState({ activeFile: null, openFiles: [], sidebarTab: 'overview' });
    useModuleProjectionStore.setState({ instances: [], status: 'error', error: 'test fallback' });
  });

  it('renders the fixed Home surface outside the optional Module registry without starting Module imports', () => {
    render(<ModuleCanvas activeTab="overview" activeWorkId={null} assistantFocusRoute={false} loaders={loaders} />);
    expect(screen.getByText('Overview content')).toBeDefined();
    expect(loaders.work).not.toHaveBeenCalled();
    expect(loaders.editor).not.toHaveBeenCalled();
  });

  it('renders the GYO focus surface without rebinding it as a Module', () => {
    render(<ModuleCanvas activeTab="sessions" activeWorkId="work-1" assistantFocusRoute loaders={loaders} />);
    expect(screen.getByText('GYO focus')).toBeDefined();
    expect(loaders.work).not.toHaveBeenCalled();
  });

  it.each(unavailableProjectionStatuses)('fails closed for business Modules while projection is %s before starting lazy imports', (status) => {
    useModuleProjectionStore.setState({
      instances: [instanceFor('documents')],
      status,
      error: status === 'error' ? 'projection unavailable' : null,
    });

    render(<ModuleCanvas activeTab="files" activeWorkId="work-1" assistantFocusRoute={false} loaders={loaders} />);

    expect(screen.getByText('Chưa thể xác minh trạng thái Module')).toBeDefined();
    expect(loaders.fileExplorer).not.toHaveBeenCalled();
    expect(loaders.editor).not.toHaveBeenCalled();
  });

  it('does not start a detached Module import from a legacy deep link and points to Settings', () => {
    useModuleProjectionStore.setState({
      instances: [instanceFor('documents', false)],
      status: 'ready',
      error: null,
    });
    render(<ModuleCanvas activeTab="files" activeWorkId="work-1" assistantFocusRoute={false} loaders={loaders} />);

    expect(screen.getByText('Module đang được tháo khỏi điều hướng')).toBeDefined();
    expect(loaders.fileExplorer).not.toHaveBeenCalled();
    expect(loaders.editor).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Mở Cài đặt Modules' }));
    expect(useHermesStore.getState().sidebarTab).toBe('settings');
  });

  it('starts an attached Module import only after projection eligibility and shows pending state', async () => {
    const deferred = deferredLoader();
    loaders.work = deferred.loader;
    useModuleProjectionStore.setState({ instances: [instanceFor('work')], status: 'ready', error: null });

    render(<ModuleCanvas activeTab="sessions" activeWorkId="work-1" assistantFocusRoute={false} loaders={loaders} />);

    expect(loaders.work).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Đang tải Công việc...')).toBeDefined();

    await act(async () => {
      deferred.resolve({ default: () => <div>Work content</div> });
      await Promise.resolve();
    });
    expect(screen.getByText('Work content')).toBeDefined();
  });

  it('keeps Monaco/editor loading outside the graph until Documents has Work plus an open file', async () => {
    useModuleProjectionStore.setState({ instances: [instanceFor('documents')], status: 'ready', error: null });

    const { rerender } = render(
      <ModuleCanvas activeTab="files" activeWorkId={null} assistantFocusRoute={false} loaders={loaders} />,
    );
    expect(screen.getByText('Chọn một Công việc để quản lý tài liệu.')).toBeDefined();
    expect(loaders.fileExplorer).not.toHaveBeenCalled();
    expect(loaders.editor).not.toHaveBeenCalled();

    rerender(<ModuleCanvas activeTab="files" activeWorkId="work-1" assistantFocusRoute={false} loaders={loaders} />);
    expect(await screen.findByText('File explorer')).toBeDefined();
    expect(loaders.fileExplorer).toHaveBeenCalledTimes(1);
    expect(loaders.editor).not.toHaveBeenCalled();

    act(() => {
      useHermesStore.setState({ activeFile: 'note.md', openFiles: ['note.md'] });
    });
    rerender(<ModuleCanvas activeTab="files" activeWorkId="work-1" assistantFocusRoute={false} loaders={loaders} />);
    expect(await screen.findByText('Editor content')).toBeDefined();
    expect(loaders.editor).toHaveBeenCalledTimes(1);
  });

  it('offers a recoverable retry when a Module import fails', async () => {
    loaders.work = vi.fn()
      .mockRejectedValueOnce(new Error('chunk unavailable'))
      .mockResolvedValueOnce({ default: () => <div>Recovered Work</div> });
    useModuleProjectionStore.setState({ instances: [instanceFor('work')], status: 'ready', error: null });

    render(<ModuleCanvas activeTab="sessions" activeWorkId="work-1" assistantFocusRoute={false} loaders={loaders} />);

    expect(await screen.findByText('Không tải được nội dung Module')).toBeDefined();
    expect(screen.getByText('chunk unavailable')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
    expect(await screen.findByText('Recovered Work')).toBeDefined();
    expect(loaders.work).toHaveBeenCalledTimes(2);
  });

  it('discards a late Module import after switching to another eligible Module', async () => {
    const deferred = deferredLoader();
    loaders.work = deferred.loader;
    useModuleProjectionStore.setState({
      instances: [instanceFor('work'), instanceFor('knowledge')],
      status: 'ready',
      error: null,
    });

    const { rerender } = render(
      <ModuleCanvas activeTab="sessions" activeWorkId="work-1" assistantFocusRoute={false} loaders={loaders} />,
    );
    expect(loaders.work).toHaveBeenCalledTimes(1);

    rerender(<ModuleCanvas activeTab="skills" activeWorkId="work-1" assistantFocusRoute={false} loaders={loaders} />);
    expect(await screen.findByText('Knowledge content')).toBeDefined();

    await act(async () => {
      deferred.resolve({ default: () => <div>Late Work</div> });
      await Promise.resolve();
    });
    await waitFor(() => expect(screen.queryByText('Late Work')).toBeNull());
    expect(screen.getByText('Knowledge content')).toBeDefined();
  });

  it('keeps Settings as a Foundation surface rendered without Module imports', () => {
    render(<ModuleCanvas activeTab="settings" activeWorkId={null} assistantFocusRoute={false} loaders={loaders} />);
    expect(screen.getByText('Settings content')).toBeDefined();
    expect(loaders.work).not.toHaveBeenCalled();
    expect(loaders.editor).not.toHaveBeenCalled();
  });
});
