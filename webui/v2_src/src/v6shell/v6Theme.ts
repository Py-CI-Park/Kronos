import { writable } from 'svelte/store';

export const V6_THEMES = [
  { id: 'inherit', labelKo: '전역 설정 따름' },
  { id: 'dark', labelKo: '다크' },
  { id: 'ocean', labelKo: '오션' },
  { id: 'forest', labelKo: '포레스트' },
  { id: 'quant-terminal', labelKo: '퀀트 터미널' },
] as const;

export type V6ThemeId = (typeof V6_THEMES)[number]['id'];
export const V6_SCALES = [0.9, 1, 1.1, 1.25] as const;
export type V6Scale = (typeof V6_SCALES)[number];

const THEME_KEY = 'kronos-v6-theme';
const SCALE_KEY = 'kronos-v6-scale';

export function normalizeV6Theme(value: unknown): V6ThemeId {
  return V6_THEMES.some((theme) => theme.id === value) ? (value as V6ThemeId) : 'inherit';
}

export function normalizeV6Scale(value: unknown): V6Scale {
  const numeric = typeof value === 'string' ? Number(value) : value;
  return V6_SCALES.includes(numeric as V6Scale) ? (numeric as V6Scale) : 1;
}

function storageAvailable(): boolean {
  try { return typeof localStorage !== 'undefined'; } catch { return false; }
}

function readStored(key: string): string | null {
  if (!storageAvailable()) return null;
  try { return localStorage.getItem(key); } catch { return null; }
}

function writeStored(key: string, value: string): void {
  if (!storageAvailable()) return;
  try {
    localStorage.setItem(key, value);
  } catch (error) {
    if (error instanceof Error) return;
    throw error;
  }
}

export const v6Theme = writable<V6ThemeId>(normalizeV6Theme(readStored(THEME_KEY)));
export const v6Scale = writable<V6Scale>(normalizeV6Scale(readStored(SCALE_KEY)));
v6Theme.subscribe((value) => writeStored(THEME_KEY, value));
v6Scale.subscribe((value) => writeStored(SCALE_KEY, String(value)));
