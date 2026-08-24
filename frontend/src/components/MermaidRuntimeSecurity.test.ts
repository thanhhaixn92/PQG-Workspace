import { beforeAll, describe, expect, it } from 'vitest';
import mermaid from 'mermaid';

const supportedSecurityRegressionCases = [
  ['flowchart', 'graph TD; A-->B;'],
  ['xy chart', 'xychart-beta\n x-axis [jan, feb]\n y-axis "Revenue" 0 --> 100\n bar [50, 60]'],
  ['radar chart', 'radar-beta\n axis m["Math"], s["Science"]\n curve a["Alice"]{80, 90}'],
  ['architecture diagram', 'architecture-beta\n group api(cloud)[API]\n service db(database)[Database] in api'],
] as const;

describe('Package E2-A Mermaid runtime security regression', () => {
  beforeAll(() => {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
    });
  });

  it.each(supportedSecurityRegressionCases)('parses a bounded %s input', async (_name, source) => {
    await expect(mermaid.parse(source, { suppressErrors: false })).resolves.toBeDefined();
  });

  it('rejects malformed input instead of treating it as a diagram', async () => {
    await expect(
      mermaid.parse('not-a-valid-mermaid-diagram', { suppressErrors: false }),
    ).rejects.toBeDefined();
  });
});
