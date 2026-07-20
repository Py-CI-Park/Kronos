import { derived } from 'svelte/store';
import { theme } from '$lib/stores';
import { v6Theme } from './v6Theme';

/** Resolve a CSS custom property against the V6 shell root so charts pick up
 *  V6-scoped themes ([data-v6-theme]) instead of only the global tokens. */
export function v6CssVar(name: string): string {
  if (typeof document === 'undefined') return 'transparent';
  const shell = document.querySelector('[data-v6-shell]') as HTMLElement | null;
  return getComputedStyle(shell ?? document.documentElement).getPropertyValue(name).trim();
}

/** Changes whenever the global light/dark theme or the V6 theme changes.
 *  Chart option `$derived` blocks reference this to re-resolve token colors. */
export const v6ChartEpoch = derived([theme, v6Theme], ([globalTheme, shellTheme]) => `${globalTheme}|${shellTheme}`);
