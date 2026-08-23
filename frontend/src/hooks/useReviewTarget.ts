import { useEffect } from 'react';

function currentReviewTarget(): string | null {
  const stored = window.sessionStorage.getItem('hermes:review-target');
  if (stored) return stored;
  if (!window.location.hash.startsWith('#review/')) return null;
  try { return decodeURIComponent(window.location.hash.slice('#review/'.length)); }
  catch { return null; }
}

export function useReviewTarget(onSource: (source: string) => void): void {
  useEffect(() => {
    const target = currentReviewTarget();
    if (!target) return;
    const separator = target.indexOf(':');
    if (separator < 1) return;
    const source = target.slice(0, separator);
    const id = target.slice(separator + 1);
    onSource(source);

    const focusTarget = () => {
      const element = document.querySelector<HTMLElement>(`[data-review-source="${CSS.escape(source)}"][data-review-id="${CSS.escape(id)}"]`);
      if (!element) return false;
      element.scrollIntoView({ block: 'center' });
      element.focus({ preventScroll: true });
      element.classList.add('review-target-highlight');
      window.setTimeout(() => element.classList.remove('review-target-highlight'), 2400);
      window.sessionStorage.removeItem('hermes:review-target');
      window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
      return true;
    };
    if (focusTarget()) return;
    const observer = new MutationObserver(() => { if (focusTarget()) observer.disconnect(); });
    observer.observe(document.body, { childList: true, subtree: true });
    const timeout = window.setTimeout(() => observer.disconnect(), 5000);
    return () => { observer.disconnect(); window.clearTimeout(timeout); };
  }, [onSource]);
}
