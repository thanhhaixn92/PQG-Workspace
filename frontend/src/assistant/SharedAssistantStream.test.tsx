import { cleanup, render, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const assistantApi = vi.hoisted(() => ({
  resolveWorkConversationAssistantThread: vi.fn(),
  createAssistantRun: vi.fn(),
  getAssistantTurns: vi.fn(),
  listAssistantThreads: vi.fn(),
  cancelAssistantTurn: vi.fn(),
  retryAssistantTurn: vi.fn(),
  getAssistantContextManifest: vi.fn(),
  assistantThreadStreamUrl: vi.fn(),
}))

const worksApi = vi.hoisted(() => ({
  listConversations: vi.fn(),
  getConversationMessages: vi.fn(),
  createConversation: vi.fn(),
  getWorkMemoryContext: vi.fn(),
  readWorkDraft: vi.fn(() => ''),
  writeWorkDraft: vi.fn(),
}))

vi.mock('../api/assistant', () => assistantApi)
vi.mock('../api/works', async () => ({ ...(await vi.importActual<object>('../api/works')), ...worksApi }))
vi.mock('../api/marketplace', () => ({ getModelConfig: vi.fn().mockResolvedValue({ models: [], providers: [] }) }))
vi.mock('../api/actionPackages', () => ({
  createActionPackage: vi.fn(),
  getWorkActionPackages: vi.fn().mockResolvedValue([]),
}))
vi.mock('../components/assistant/TurnPartRenderer', () => ({
  TurnPartRenderer: () => null,
  AssistantTurnCard: () => null,
}))
vi.mock('../components/HermesAssistantPanel', () => ({ TurnPartRenderer: () => null }))
vi.mock('../components/FileExplorer', () => ({ FileExplorer: () => null }))
vi.mock('../components/EditorPanel', () => ({ EditorPanel: () => null }))
vi.mock('../components/ReportsPanel', () => ({ ReportsPanel: () => null }))
vi.mock('../components/KnowledgePanel', () => ({ KnowledgePanel: () => null }))
vi.mock('../components/ActionPackagesPanel', () => ({ ActionPackagesPanel: () => null }))
vi.mock('../components/PhaseCard', () => ({ PhaseCard: () => null }))

import { AssistantChatSidebar } from '../components/AssistantChatSidebar'
import { ConversationWorkspace } from '../components/WorkHub'
import { useHermesStore } from '../store/store'
import { __resetForTests } from './threadStreamRegistry'

const WORK = { id: 'work-a', title: 'Work A', workspace_path: 'C:/a', created_at: 1, updated_at: 1 }
const CONVERSATION = { id: 'conv-a1', session_id: 'work-a', title: 'A1', status: 'active' as const, created_at: 1, updated_at: 1, message_count: 0 }
const THREAD = { id: 'thread-a1', title: 'GYO', work_id: 'work-a', conversation_id: 'conv-a1', status: 'active' as const, created_at: 1, updated_at: 1 }
const runningTurns = [{
  id: 'assistant-turn', thread_id: 'thread-a1', work_id: 'work-a', conversation_id: 'conv-a1',
  role: 'assistant' as const, status: 'running' as const, created_at: 1, parts: [],
}]

const sources: Array<{ url: string; closed: boolean }> = []
class MockEventSource {
  url: string
  constructor(url: string) {
    this.url = url
    sources.push({ url, closed: false })
  }
  addEventListener() {}
  close() {
    const source = sources.find(item => item.url === this.url && !item.closed)
    if (source) source.closed = true
  }
}

function Surfaces({ sidebar = true }: { sidebar?: boolean }) {
  return <>
    {sidebar && <AssistantChatSidebar />}
    <ConversationWorkspace workId="work-a" conversation={CONVERSATION} onRename={vi.fn()} onArchive={vi.fn()} />
  </>
}

describe('shared assistant stream across Sidebar and WorkHub', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    __resetForTests()
    sources.length = 0
    vi.stubGlobal('EventSource', MockEventSource)
    useHermesStore.setState({
      sessions: [WORK], activeSessionId: WORK.id,
      assistantSidebarMode: 'expanded', assistantSidebarWidth: 380,
    })
    worksApi.listConversations.mockResolvedValue([CONVERSATION])
    worksApi.getConversationMessages.mockResolvedValue({ messages: [], has_more: false })
    assistantApi.listAssistantThreads.mockResolvedValue([THREAD])
    assistantApi.getAssistantTurns.mockResolvedValue(runningTurns)
    assistantApi.getAssistantContextManifest.mockResolvedValue(null)
  })

  afterEach(() => {
    cleanup()
    __resetForTests()
    vi.unstubAllGlobals()
  })

  it('keeps one EventSource alive when Sidebar unsubscribes but WorkHub still subscribes', async () => {
    const view = render(<Surfaces />)
    await waitFor(() => expect(sources).toHaveLength(1))
    expect(sources[0].closed).toBe(false)

    view.rerender(<Surfaces sidebar={false} />)

    await waitFor(() => expect(sources[0].closed).toBe(false))
    expect(sources).toHaveLength(1)
  })

  it('does not open a stream when persisted turns are already terminal', async () => {
    assistantApi.getAssistantTurns.mockResolvedValue(runningTurns.map(turn => ({ ...turn, status: 'completed' })))
    render(<Surfaces />)
    await waitFor(() => expect(assistantApi.getAssistantTurns).toHaveBeenCalled())
    expect(sources).toHaveLength(0)
  })
})
