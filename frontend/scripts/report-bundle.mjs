import fs from 'node:fs';
import path from 'node:path';
import { gzipSync } from 'node:zlib';

const distDir = path.resolve(process.cwd(), 'dist');
const srcDir = path.resolve(process.cwd(), 'src');
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
  const matches = records.filter(([key, record]) => {
    const normalizedKey = normalizeManifestPath(key);
    const normalizedRecordSource = normalizeManifestPath(record?.src);
    return normalizedKey === normalizedSourcePath
      || normalizedKey.endsWith(normalizedSourcePath)
      || normalizedRecordSource === normalizedSourcePath
      || normalizedRecordSource.endsWith(normalizedSourcePath);
  });
  if (matches.length > 1) {
    throw new Error(`A2 bundle gate found ambiguous manifest source entries for ${sourcePath}`);
  }
  return matches.length === 1 ? { key: matches[0][0], record: matches[0][1] } : null;
}

function findOutputChunk(outputStem) {
  const matches = records.filter(([, record]) => {
    if (!record?.file?.endsWith('.js')) return false;
    const basename = path.posix.basename(normalizeManifestPath(record.file));
    return basename.startsWith(`${outputStem}-`);
  });
  if (matches.length > 1) {
    throw new Error(`A2 bundle gate found ambiguous output chunks for ${outputStem}`);
  }
  return matches.length === 1 ? { key: matches[0][0], record: matches[0][1] } : null;
}

function runtimeSourceFiles(directory) {
  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...runtimeSourceFiles(absolute));
      continue;
    }
    if (!/\.(?:[cm]?[jt]sx?)$/.test(entry.name)) continue;
    if (/\.(?:test|spec)\.[cm]?[jt]sx?$/.test(entry.name)) continue;
    files.push(absolute);
  }
  return files;
}

function findRuntimeImportSources(needle) {
  return runtimeSourceFiles(srcDir)
    .filter(file => fs.readFileSync(file, 'utf8').includes(needle))
    .map(file => normalizeManifestPath(path.relative(process.cwd(), file)))
    .sort();
}

const editorBoundary = findSourceEntry('src/foundation/shell/EditorSurface.tsx');
const editorPanelChunk = findOutputChunk('EditorPanel');
const mermaidEntry = findSourceEntry('src/components/MermaidDiagram.tsx');
const monacoImportSources = findRuntimeImportSources('@monaco-editor/react');
const editorBoundaryGraph = editorBoundary ? collectStaticGraph([editorBoundary.key]) : new Set();
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
  monacoImportSources,
  monacoEditorEntry: editorBoundary?.key ?? null,
  monacoEditorSource: editorBoundary?.record?.src ?? null,
  monacoEditorFile: editorBoundary?.record?.file ?? null,
  monacoEditorIsDynamicEntry: editorBoundary?.record?.isDynamicEntry ?? false,
  monacoInInitialGraph: editorBoundary ? eagerKeys.has(editorBoundary.key) : null,
  editorPanelChunk: editorPanelChunk?.key ?? null,
  editorPanelFile: editorPanelChunk?.record?.file ?? null,
  editorPanelInEditorBoundaryGraph: editorPanelChunk ? editorBoundaryGraph.has(editorPanelChunk.key) : null,
  editorPanelInInitialGraph: editorPanelChunk ? eagerKeys.has(editorPanelChunk.key) : null,
  mermaidEntry: mermaidEntry?.key ?? null,
  mermaidSource: mermaidEntry?.record?.src ?? null,
  mermaidFile: mermaidEntry?.record?.file ?? null,
  mermaidIsDynamicEntry: mermaidEntry?.record?.isDynamicEntry ?? false,
  mermaidInInitialGraph: mermaidEntry ? eagerKeys.has(mermaidEntry.key) : null,
};

console.log(`PQG_BUNDLE_RECEIPT_JSON=${JSON.stringify(receipt)}`);

if (monacoImportSources.length !== 1 || monacoImportSources[0] !== 'src/components/EditorPanel.tsx') {
  throw new Error(`A2 bundle gate failed: Monaco runtime imports are not isolated to EditorPanel (${monacoImportSources.join(', ') || 'none'})`);
}
if (!editorBoundary) {
  throw new Error('A2 bundle gate could not find EditorSurface dynamic entry in manifest');
}
if (!editorBoundary.record?.isDynamicEntry) {
  throw new Error('A2 bundle gate failed: EditorSurface is not a dynamic manifest entry');
}
if (eagerKeys.has(editorBoundary.key)) {
  throw new Error('A2 bundle gate failed: EditorSurface remains in the initial static graph');
}
if (!editorPanelChunk) {
  throw new Error('A2 bundle gate could not find EditorPanel output chunk');
}
if (!editorBoundaryGraph.has(editorPanelChunk.key)) {
  throw new Error('A2 bundle gate failed: EditorPanel is not downstream of the dynamic EditorSurface boundary');
}
if (eagerKeys.has(editorPanelChunk.key)) {
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
