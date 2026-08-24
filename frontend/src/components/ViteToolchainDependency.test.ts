import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

interface LockPackage {
  dependencies?: Record<string, string>
  version?: string
}

interface PackageLock {
  lockfileVersion: number
  packages: Record<string, LockPackage>
}

function versionAtLeast(version: string | undefined, floor: [number, number, number]) {
  if (!version) return false

  const current = version.split('.').map(Number)
  return current[0] > floor[0]
    || (current[0] === floor[0] && current[1] > floor[1])
    || (current[0] === floor[0] && current[1] === floor[1] && current[2] >= floor[2])
}

describe('E2-C Vite dev-toolchain dependency remediation', () => {
  const frontendRoot = resolve(__dirname, '../..')
  const manifest = JSON.parse(readFileSync(resolve(frontendRoot, 'package.json'), 'utf8')) as {
    devDependencies: Record<string, string>
  }
  const lock = JSON.parse(readFileSync(resolve(frontendRoot, 'package-lock.json'), 'utf8')) as PackageLock

  it('keeps Vite in major 8 while resolving the approved PostCSS and Nanoid floors', () => {
    const vite = lock.packages['node_modules/vite']
    const postcss = lock.packages['node_modules/postcss']
    const nanoid = lock.packages['node_modules/nanoid']

    expect(manifest.devDependencies.vite).toBe('^8.2.2')
    expect(vite?.version).toBe('8.2.2')
    expect(vite?.dependencies?.postcss).toBe('^8.5.26')
    expect(versionAtLeast(postcss?.version, [8, 5, 23])).toBe(true)
    expect(versionAtLeast(nanoid?.version, [3, 3, 18])).toBe(true)
  })

  it('does not fold the separately gated Monaco or jsdom/Undici packages into E2-C', () => {
    expect(lock.packages['node_modules/monaco-editor']?.version).toBe('0.55.1')
    expect(lock.packages['node_modules/dompurify']?.version).toBe('3.2.7')
    expect(lock.packages['node_modules/jsdom']?.version).toBe('29.1.1')
    expect(lock.packages['node_modules/undici']?.version).toBe('7.28.0')
  })
})
