import { describe, it, expect, vi, beforeEach } from 'vitest'

let lastSourceUrl = ''
const sourceListeners: Record<string, Record<string, ((e: { data: string }) => void)[]>> = {}
const openSources: Array<{ url: string; close: () => void; closed: boolean }> = []

class MockEventSource {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSED = 2
  url: string
  readyState = 0
  closed = false

  constructor(url: string) {
    this.url = url
    lastSourceUrl = url
    sourceListeners[url] = {}
    openSources.push({ url, closed: false, close: () => { this.closed = true; this.readyState = 2 } })
  }
  addEventListener(type: string, cb: (e: { data: string }) => void) {
    if (!sourceListeners[this.url][type]) sourceListeners[this.url][type] = []
    sourceListeners[this.url][type].push(cb)
  }
  removeEventListener() {}
  close() {
    this.closed = true
    this.readyState = 2
    const s = openSources.find(x => x.url === this.url)
    if (s) s.closed = true
  }
}

vi.stubGlobal('EventSource', MockEventSource)

import {
  subscribeThreadStream,
  activeStreamCount,
  __resetForTests,
} from '../assistant/threadStreamRegistry'

function fireEvent(url: string, type: string, data: string) {
  ;(sourceListeners[url]?.[type] || []).forEach((cb) => cb({ data }))
}

describe('threadStreamRegistry', () => {
  beforeEach(() => {
    lastSourceUrl = ''
    openSources.length = 0
    Object.keys(sourceListeners).forEach((k) => delete sourceListeners[k])
    __resetForTests()
  })

  it('creates exactly one EventSource per thread', () => {
    const unsub1 = subscribeThreadStream('t1', vi.fn())
    const unsub2 = subscribeThreadStream('t1', vi.fn())
    expect(openSources.filter((s) => s.url.includes('t1')).length).toBe(1)
    unsub1()
    unsub2()
  })

  it('closes stream when last subscriber unsubscribes', () => {
    const unsub1 = subscribeThreadStream('t1', vi.fn())
    const unsub2 = subscribeThreadStream('t1', vi.fn())
    unsub1()
    expect(openSources[0].closed).toBe(false)
    unsub2()
    expect(openSources[0].closed).toBe(true)
    expect(activeStreamCount()).toBe(0)
  })

  it('delivers events to all subscribers', () => {
    const sub1 = vi.fn()
    const sub2 = vi.fn()
    subscribeThreadStream('t1', sub1)
    subscribeThreadStream('t1', sub2)
    fireEvent(lastSourceUrl, 'token', 'hello')
    expect(sub1).toHaveBeenCalledWith({ type: 'token', data: 'hello' })
    expect(sub2).toHaveBeenCalledWith({ type: 'token', data: 'hello' })
  })

  it('auto-closes on done event', () => {
    const sub = vi.fn()
    subscribeThreadStream('t1', sub)
    fireEvent(lastSourceUrl, 'done', '{}')
    expect(sub).toHaveBeenCalledWith({ type: 'done', data: '{}' })
    expect(activeStreamCount()).toBe(0)
  })

  it('auto-closes on error event', () => {
    const sub = vi.fn()
    subscribeThreadStream('t1', sub)
    fireEvent(lastSourceUrl, 'error', '{}')
    expect(sub).toHaveBeenCalledWith({ type: 'error', data: '{}' })
    expect(activeStreamCount()).toBe(0)
  })

  it('does not deliver events after unsubscribe', () => {
    const sub = vi.fn()
    const unsub = subscribeThreadStream('t1', sub)
    unsub()
    fireEvent(lastSourceUrl, 'token', 'late')
    expect(sub).not.toHaveBeenCalled()
  })

  it('creates new stream after close for same thread', () => {
    const unsub1 = subscribeThreadStream('t1', vi.fn())
    unsub1()
    expect(openSources[0].closed).toBe(true)
    subscribeThreadStream('t1', vi.fn())
    expect(openSources.length).toBe(2)
    expect(openSources[1].closed).toBe(false)
  })
})
