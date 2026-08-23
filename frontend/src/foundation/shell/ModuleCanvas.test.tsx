import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useHermesStore } from '../../store/store';
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

describe('ModuleCanvas', () => {
  beforeEach(() => {
    useHermesStore.setState({ activeFile: null, openFiles: [] });
  });

  it('renders the fixed Home surface outside the optional Module registry', () => {
    render(<ModuleCanvas activeTab="overview" activeWorkId={null} assistantFocusRoute={false} />);
    expect(screen.getByText('Overview content')).toBeDefined();
  });

  it('renders the GYO focus surface without rebinding it as a Module', () => {
    render(<ModuleCanvas activeTab="sessions" activeWorkId="work-1" assistantFocusRoute />);
    expect(screen.getByText('GYO focus')).toBeDefined();
  });

  it('keeps document editing guarded by Work and open-file state', () => {
    const { rerender } = render(<ModuleCanvas activeTab="files" activeWorkId={null} assistantFocusRoute={false} />);
    expect(screen.getByText('Chọn một Công việc để quản lý tài liệu.')).toBeDefined();

    useHermesStore.setState({ activeFile: 'note.md', openFiles: ['note.md'] });
    rerender(<ModuleCanvas activeTab="files" activeWorkId="work-1" assistantFocusRoute={false} />);
    expect(screen.getByText('File explorer')).toBeDefined();
    expect(screen.getByText('Editor content')).toBeDefined();
  });

  it('keeps Settings as a Foundation surface rendered by the canvas switch', () => {
    render(<ModuleCanvas activeTab="settings" activeWorkId={null} assistantFocusRoute={false} />);
    expect(screen.getByText('Settings content')).toBeDefined();
  });
});
