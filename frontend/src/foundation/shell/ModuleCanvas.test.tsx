import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ModuleInstance } from '../../api/modules';
import { useHermesStore } from '../../store/store';
import { useModuleProjectionStore } from '../modules/store';
import { ModuleCanvas } from './ModuleCanvas';

vi.mock('../../components/AssistantChatSidebar', () => ({ AssistantChatSidebar: ({ surfaceMode }: { surfaceMode?: string }) => <div>GYO {surfaceMode ?? 'drawer'}</div> }));
vi.mock('../../components/OverviewPanel', () => ({ OverviewPanel: () => <div>Overview content</div> }));
vi.mock('../../components/WorkWorkspace', () => ({ WorkWorkspace: () => <div>Work content</div> }));
vi.mock('../../components/FileExplorer', () => ({ FileExplorer: () => <div>File explorer</div> }));
vi.mock('../../components/EditorPanel', () => ({ EditorPanel: () => <div>Editor content</div> }));
vi.mock('../../components/KnowledgePanel', () => ({ KnowledgePanel: () => <div>Knowledge content</div> }));
vi.mock('../../components/ReportsPanel', () => ({ ReportsPanel: () => <div>Reports content</div> }));
vi.mock('../../components/ReviewInboxPanel', () => ({ ReviewInboxPanel: () => <div>Review content</div> }));
vi.mock('../../components/SettingsPanel', () => ({ SettingsPanel: () => <div>Settings content</div> }));
vi.mock('../../components/MemoryPanel', () => ({ MemoryPanel: () => <div>Memory content</div> }));
vi.mock('../../components/MemoryHubPanel', () => ({ MemoryHubPanel: () => <div>Memory Hub content</div> }));
vi.mock('../../components/LocalDataPanel', () => ({ LocalDataPanel: () => <div>Local data content</div> }));
vi.mock('../../components/DirapPanel', () => ({ DirapPanel: () => <div>Research content</div> }));

const documentsInstance = (attached: boolean): ModuleInstance => ({
  id: 'builtin:documents',
  module_id: 'documents',
  source_kind: 'builtin',
  package_id: null,
  display_name: 'Tài liệu',
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

describe('ModuleCanvas', () => {
  beforeEach(() => {
    useHermesStore.setState({ activeFile: null, openFiles: [], sidebarTab: 'overview' });
    useModuleProjectionStore.setState({ instances: [], status: 'error', error: 'test fallback' });
  });

  it('renders the fixed Home surface outside the optional Module registry', () => {
    render(<ModuleCanvas activeTab="overview" activeWorkId={null} assistantFocusRoute={false} />);
    expect(screen.getByText('Overview content')).toBeDefined();
  });

  it('renders the GYO focus surface without rebinding it as a Module', () => {
    render(<ModuleCanvas activeTab="sessions" activeWorkId="work-1" assistantFocusRoute />);
    expect(screen.getByText('GYO focus')).toBeDefined();
  });

  it.each(unavailableProjectionStatuses)('fails closed for business Modules while projection is %s', (status) => {
    useModuleProjectionStore.setState({
      instances: [documentsInstance(true)],
      status,
      error: status === 'error' ? 'projection unavailable' : null,
    });

    render(<ModuleCanvas activeTab="files" activeWorkId="work-1" assistantFocusRoute={false} />);

    expect(screen.getByText('Chưa thể xác minh trạng thái Module')).toBeDefined();
    expect(screen.queryByText('File explorer')).toBeNull();
    expect(screen.queryByText('Editor content')).toBeNull();
  });

  it('keeps document editing guarded by Work and open-file state after projection is verified', () => {
    useModuleProjectionStore.setState({
      instances: [documentsInstance(true)],
      status: 'ready',
      error: null,
    });

    const { rerender } = render(<ModuleCanvas activeTab="files" activeWorkId={null} assistantFocusRoute={false} />);
    expect(screen.getByText('Chọn một Công việc để quản lý tài liệu.')).toBeDefined();

    act(() => {
      useHermesStore.setState({ activeFile: 'note.md', openFiles: ['note.md'] });
    });
    rerender(<ModuleCanvas activeTab="files" activeWorkId="work-1" assistantFocusRoute={false} />);
    expect(screen.getByText('File explorer')).toBeDefined();
    expect(screen.getByText('Editor content')).toBeDefined();
  });

  it('does not render a detached Module from a legacy deep link and points to Settings', () => {
    useModuleProjectionStore.setState({
      instances: [documentsInstance(false)],
      status: 'ready',
      error: null,
    });
    render(<ModuleCanvas activeTab="files" activeWorkId="work-1" assistantFocusRoute={false} />);

    expect(screen.getByText('Module đang được tháo khỏi điều hướng')).toBeDefined();
    expect(screen.queryByText('File explorer')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Mở Cài đặt Modules' }));
    expect(useHermesStore.getState().sidebarTab).toBe('settings');
  });

  it('keeps Settings as a Foundation surface rendered by the canvas switch', () => {
    render(<ModuleCanvas activeTab="settings" activeWorkId={null} assistantFocusRoute={false} />);
    expect(screen.getByText('Settings content')).toBeDefined();
  });
});
