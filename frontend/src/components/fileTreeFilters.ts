import type { FileNode } from '../api/files';

const TEST_DATA_MARKERS = ['uat-codex-', 'smoke-test-', '404test-'];

export const isTestDataNode = (node: FileNode) => TEST_DATA_MARKERS.some(marker => node.name.toLowerCase().startsWith(marker));

export const filterTestDataNodes = (nodes: FileNode[]): FileNode[] => nodes
  .filter(node => !isTestDataNode(node))
  .map(node => node.children ? { ...node, children: filterTestDataNodes(node.children) } : node);

export const countTestDataNodes = (nodes: FileNode[]): number => nodes.reduce(
  (total, node) => total + (isTestDataNode(node) ? 1 : 0) + (node.children ? countTestDataNodes(node.children) : 0),
  0,
);
