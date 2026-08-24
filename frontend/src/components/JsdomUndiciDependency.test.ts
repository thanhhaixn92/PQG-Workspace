import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

interface LockPackage {
  dependencies?: Record<string, string>
  version?: string
}

interface PackageLock {
  packages: Record<string, LockPackage>
}

function versionAtLeast(version: string | undefined, floor: [number, number, number]) {
  if (!version) return false

  const current = version.split('.').map(Number)
  return current[0] > floor[0]
    || (current[0] === floor[0] && current[1] > floor[1])
    || (current[0] === floor[0] && current[1] === floor[1] && current[2] >= floor[2])
}

describe('E2-D jsdom/Undici test-environment dependency remediation', () => {
  const frontendRoot = resolve(__dirname, '../..')
  const manifest = JSON.parse(readFileSync(resolve(frontendRoot, 'package.json'), 'utf8')) as {
    devDependencies: Record<string, string>
  }
  const lock = JSON.parse(readFileSync(resolve(frontendRoot, 'package-lock.json'), 'utf8')) as PackageLock

  it('keeps jsdom in the approved 29.x line while resolving Undici at the safe floor', () => {
    const jsdom = lock.packages['node_modules/jsdom']
    const undici = lock.packages['node_modules/undici']

    expect(manifest.devDependencies.jsdom).toBe('^29.1.1')
    expect(jsdom?.version).toBe('29.1.1')
    expect(jsdom?.dependencies?.undici).toBe('^7.25.0')
    expect(versionAtLeast(undici?.version, [7, 29, 0])).toBe(true)
  })

  it('retains separately gated E2-B and E2-C resolutions', () => {
    expect(lock.packages['node_modules/monaco-editor']?.version).toBe('0.55.1')
    expect(lock.packages['node_modules/dompurify']?.version).toBe('3.2.7')
    expect(lock.packages['node_modules/vite']?.version).toBe('8.2.2')
    expect(versionAtLeast(lock.packages['node_modules/postcss']?.version, [8, 5, 23])).toBe(true)
    expect(versionAtLeast(lock.packages['node_modules/nanoid']?.version, [3, 3, 18])).toBe(true)
  })
})
