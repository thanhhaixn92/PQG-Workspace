export type StreamEvent = { type: 'token' | 'done' | 'error'; data: string }
export type StreamSubscriber = (event: StreamEvent) => void

interface StreamEntry {
  source: EventSource
  subscribers: Set<StreamSubscriber>
  closed: boolean
}

const streams = new Map<string, StreamEntry>()

export function subscribeThreadStream(threadId: string, subscriber: StreamSubscriber): () => void {
  if (typeof EventSource === 'undefined') return () => {}
  let entry = streams.get(threadId)
  if (!entry || entry.closed) {
    const base = (() => { try { return (import.meta as any).env?.VITE_API_BASE_URL || '' } catch { return '' } })()
    const source = new EventSource(`${base}/api/assistant/threads/${threadId}/stream`)
    entry = { source, subscribers: new Set(), closed: false }
    source.addEventListener('token', (e) => {
      if (entry!.closed) return
      const data = (e as MessageEvent).data
      entry!.subscribers.forEach((s) => s({ type: 'token', data }))
    })
    source.addEventListener('done', (e) => {
      if (entry!.closed) return
      const data = (e as MessageEvent).data
      entry!.subscribers.forEach((s) => s({ type: 'done', data }))
      closeThreadStream(threadId)
    })
    source.addEventListener('error', (e) => {
      if (entry!.closed) return
      const data = (e as MessageEvent).data
      entry!.subscribers.forEach((s) => s({ type: 'error', data }))
      closeThreadStream(threadId)
    })
    streams.set(threadId, entry)
  }
  entry.subscribers.add(subscriber)
  return () => {
    entry!.subscribers.delete(subscriber)
    if (entry!.subscribers.size === 0) closeThreadStream(threadId)
  }
}

export function closeThreadStream(threadId: string): void {
  const entry = streams.get(threadId)
  if (!entry || entry.closed) return
  entry.closed = true
  entry.source.close()
  streams.delete(threadId)
}

export function activeStreamCount(): number {
  return streams.size
}

export function __resetForTests(): void {
  streams.clear()
}
