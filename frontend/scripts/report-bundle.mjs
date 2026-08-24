import fs from 'node:fs';
import path from 'node:path';
import { gzipSync } from 'node:zlib';

const distDir = path.resolve(process.cwd(), 'dist');
const manifestPath = path.join(distDir, '.vite', 'manifest.json');
const MAX_EAGER_CHUNK_BYTES = 500 * 1024;

if (!fs.existsSync(manifestPath)) {
  throw new Error(`Bundle manifest not found: ${manifestPath}`);
}

const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const records = Object.entries(manifest);
const entryKeys = records.filter(([, value]) => value.isEntry).map(([key]) => key);

if (entryKeys.length === 0) {
  throw new Error('Bundle manifest has no entry chunk');
}

function collectStaticGraph(keys) {
  const visited = new Set();
  const stack = [...keys];
  while (stack.length > 0) {
    const key = stack.pop();
    if (!key || visited.has(key)) continue;
    const record = manifest[key];
    if (!record) continue;
    visited.add(key);
    for (const imported of record.imports ?? []) stack.push(imported);
  }
  return visited;
}

function jsAssetFor(key) {
  const record = manifest[key];
  if (!record?.file?.endsWith('.js')) return null;
  const filePath = path.join(distDir, record.file);
  const bytes = fs.statSync(filePath).size;
  const gzipBytes = gzipSync(fs.readFileSync(filePath)).byteLength;
  return { key, file: record.file, bytes, gzipBytes };
}

const eagerKeys = collectStaticGraph(entryKeys);
const eagerAssets = [...eagerKeys].map(jsAssetFor).filter(Boolean);
const allJsAssets = records.map(([key]) => jsAssetFor(key)).filter(Boolean);
const lazyAssets = allJsAssets.filter(asset => !eagerKeys.has(asset.key));

function largest(assets) {
  return [...assets].sort((a, b) => b.bytes - a.bytes)[0] ?? null;
}

function total(assets, field) {
  return assets.reduce((sum, asset) => sum + asset[field], 0);
}

function normalizeManifestPath(value) {
  return typeof value === 'string' ? value.replaceAll('\\', '/') : '';
}

function findSourceEntry(sourcePath) {
  const normalizedSourcePath = normalizeManifestPath(sourcePath);
  const match = records.find(([key, record]) => {
    const normalizedKey = normalizeManifestPath(key);
    const normalizedRecordSource = normalizeManifestPath(record?.src);
    return normalizedKey === normalizedSourcePath
      || normalizedKey.endsWith(normalizedSourcePath)
      || normalizedRecordSource === normalizedSourcePath
      || normalizedRecordSource.endsWith(normalizedSourcePath);
  });
  return match ? { key: match[0], record: match[1] } : null;
}

const monacoEntry = findSourceEntry('src/components/EditorPanel.tsx');
const mermaidEntry = findSourceEntry('src/components/MermaidDiagram.tsx');
const entryAssets = entryKeys.map(jsAssetFor).filter(Boolean);
const largestEager = largest(eagerAssets);
const largestLazy = largest(lazyAssets);

const receipt = {
  entry: entryAssets,
  initialJsRequestCount: eagerAssets.length,
  initialJsBytes: total(eagerAssets, 'bytes'),
  initialJsGzipBytes: total(eagerAssets, 'gzipBytes'),
  largestEager,
  largestLazy,
  monacoEditorEntry: monacoEntry?.key ?? null,
  monacoEditorSource: monacoEntry?.record?.src ?? null,
  monacoEditorIsDynamicEntry: monacoEntry?.record?.isDynamicEntry ?? false,
  monacoInInitialGraph: monacoEntry ? eagerKeys.has(monacoEntry.key) : null,
  mermaidEntry: mermaidEntry?.key ?? null,
  mermaidSource: mermaidEntry?.record?.src ?? null,
  mermaidIsDynamicEntry: mermaidEntry?.record?.isDynamicEntry ?? false,
  mermaidInInitialGraph: mermaidEntry ? eagerKeys.has(mermaidEntry.key) : null,
};

console.log(`PQG_BUNDLE_RECEIPT_JSON=${JSON.stringify(receipt)}`);

if (!monacoEntry) {
  throw new Error('A2 bundle gate could not find EditorPanel dynamic entry in manifest');
}
if (!monacoEntry.record?.isDynamicEntry) {
  throw new Error('A2 bundle gate failed: EditorPanel is not a dynamic manifest entry');
}
if (eagerKeys.has(monacoEntry.key)) {
  throw new Error('A2 bundle gate failed: EditorPanel/Monaco remains in the initial static graph');
}
if (!mermaidEntry) {
  throw new Error('A2 bundle gate could not find MermaidDiagram dynamic entry in manifest');
}
if (!mermaidEntry.record?.isDynamicEntry) {
  throw new Error('A2 bundle gate failed: MermaidDiagram is not a dynamic manifest entry');
}
if (eagerKeys.has(mermaidEntry.key)) {
  throw new Error('A2 bundle gate failed: MermaidDiagram remains in the initial static graph');
}
if (largestEager && largestEager.bytes >= MAX_EAGER_CHUNK_BYTES) {
  throw new Error(`A2 bundle gate failed: largest eager chunk ${largestEager.file} is ${largestEager.bytes} bytes (limit ${MAX_EAGER_CHUNK_BYTES})`);
}
