const INTERNAL_ROUTE_PREFIXES: ReadonlyArray<string> = ['/work/', '/artifacts/'];

const hasForbiddenControlCharacter = (value: string): boolean =>
  Array.from(value).some(character => {
    const codePoint = character.codePointAt(0);
    return codePoint !== undefined
      && (codePoint <= 0x1F || (codePoint >= 0x7F && codePoint <= 0x9F));
  });

export function resolveSafeUri(uri: string): { safe: true; external: boolean; target: string } | { safe: false } {
  const raw = uri || '';
  if (!raw || !raw.trim() || hasForbiddenControlCharacter(raw)) return { safe: false };

  const trimmed = raw.trim();
  if (trimmed.startsWith('//') || trimmed.startsWith('\\\\') || trimmed.includes('\\')) return { safe: false };

  for (const prefix of INTERNAL_ROUTE_PREFIXES) {
    if (trimmed.startsWith(prefix)) return { safe: true, external: false, target: trimmed };
  }

  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return { safe: true, external: true, target: trimmed };
    }
  } catch {
    return { safe: false };
  }

  return { safe: false };
}

export function openSafeUri(uri: string): void {
  const resolved = resolveSafeUri(uri);
  if (!resolved.safe) return;
  if (resolved.external) window.open(resolved.target, '_blank', 'noopener,noreferrer');
  else window.location.href = resolved.target;
}
