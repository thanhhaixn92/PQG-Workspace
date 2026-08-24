import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

interface LockPackage {
  version?: string;
  dependencies?: Record<string, string>;
}

interface PackageLock {
  packages: Record<string, LockPackage>;
}

const readJson = <T>(relativePath: string): T =>
  JSON.parse(readFileSync(resolve(process.cwd(), relativePath), 'utf8')) as T;

const versionTuple = (version: string): [number, number, number] => {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(version);
  if (!match) {
    throw new Error(`Expected a stable semantic version, received ${version}`);
  }

  return [Number(match[1]), Number(match[2]), Number(match[3])];
};

const isAtLeast = (actual: string, minimum: string): boolean => {
  const actualParts = versionTuple(actual);
  const minimumParts = versionTuple(minimum);

  for (let index = 0; index < actualParts.length; index += 1) {
    const part = actualParts[index];
    if (part !== minimumParts[index]) {
      return part > minimumParts[index];
    }
  }

  return true;
};

describe('Package E2-A Mermaid dependency boundary', () => {
  const manifest = readJson<{ dependencies: Record<string, string> }>('package.json');
  const lock = readJson<PackageLock>('package-lock.json');

  it('pins Mermaid at the approved fixed release', () => {
    expect(manifest.dependencies.mermaid).toBe('11.16.1');
    expect(lock.packages['node_modules/mermaid']?.version).toBe('11.16.1');
  });

  it('keeps Mermaid runtime DOMPurify at or above the E1 safe floor', () => {
    const version = lock.packages['node_modules/mermaid/node_modules/dompurify']?.version;

    expect(version).toBeDefined();
    expect(isAtLeast(version!, '3.4.13')).toBe(true);
  });

  it('does not mutate the separately gated Monaco DOMPurify branch', () => {
    expect(lock.packages['node_modules/monaco-editor']?.dependencies?.dompurify).toBe('3.2.7');
    expect(lock.packages['node_modules/dompurify']?.version).toBe('3.2.7');
  });
});
