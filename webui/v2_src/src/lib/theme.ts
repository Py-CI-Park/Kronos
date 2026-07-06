// design_spec §3 - Theme tokens owner.
// ECharts 와 Plotly 가 동일 토큰을 사용하도록 한 파일에서 옵션을 만든다.
// F2: 색상은 하드코딩하지 않고 canonical CSS custom property (core.css) 에서
//     render time 에 읽어온다. => [data-theme] 플립 시 자동으로 라이트/다크 반영.

// CSS 변수가 비어있거나 (SSR / no-DOM) 해석 불가할 때 사용할 fallback 값.
// 기존 하드코딩 팔레트를 그대로 보존한다.
const FALLBACKS = {
  bg: '#0f172a',
  card: '#111827',
  cardRaised: '#0b1120',
  border: '#243244',
  borderMuted: '#1e293b',
  text: '#e2e8f0',
  textMuted: '#94a3b8',
  textDim: '#64748b',
  textFaint: '#475569',
  accent: '#38bdf8',
  accentDim: 'rgba(56,189,248,.12)',
  accentHover: 'rgba(56,189,248,.08)',
  accentSubtle: '#bfdbfe',
  success: '#22c55e',
  successBg: '#14532d',
  successText: '#dcfce7',
  warn: '#f59e0b',
  warnBg: '#422006',
  warnText: '#fde68a',
  danger: '#ef4444',
  info: '#93c5fd',
  infoBg: '#0c4a6e',
} as const;

export type ThemeColors = Record<keyof typeof FALLBACKS, string>;

// 각 색상 키 -> canonical CSS 변수(core.css) 매핑.
const VAR_MAP: Record<keyof typeof FALLBACKS, string> = {
  bg: '--bg',
  card: '--surface',
  cardRaised: '--surface-raised',
  border: '--border',
  borderMuted: '--border-faint',
  text: '--fg',
  textMuted: '--muted',
  textDim: '--dim',
  textFaint: '--faint',
  accent: '--accent',
  accentDim: '--accent-soft',
  accentHover: '--accent-soft',
  accentSubtle: '--accent-tint',
  success: '--success',
  successBg: '--success-soft',
  successText: '--success',
  warn: '--warn',
  warnBg: '--warn-soft',
  warnText: '--warn',
  danger: '--danger',
  info: '--info',
  infoBg: '--info-soft',
};

// documentElement 에서 CSS 변수를 읽어 trim. 값이 없으면 fallback.
function resolveVar(name: string, fallback: string): string {
  if (typeof document === 'undefined' || typeof getComputedStyle === 'undefined') {
    return fallback;
  }
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

// 호출 시점(render time)에 canonical 토큰을 해석한 색상 세트.
export function getColors(): ThemeColors {
  const out = {} as ThemeColors;
  (Object.keys(FALLBACKS) as (keyof typeof FALLBACKS)[]).forEach((key) => {
    out[key] = resolveVar(VAR_MAP[key], FALLBACKS[key]);
  });
  return out;
}

export const theme = {
  // getter — 접근할 때마다 CSS 변수에서 live 로 재해석된다.
  get colors(): ThemeColors {
    return getColors();
  },
  typography: {
    fontBase: "'Segoe UI','Malgun Gothic',sans-serif",
    fontMono: "'Consolas','D2Coding',monospace",
  },
} as const;

// CSS 변수를 :root 에 set — Tailwind 와 별개로 ECharts/Plotly 가 직접 읽을 수 있게.
export function applyThemeToDocument(): void {
  if (typeof document === 'undefined') return;
  const colors = getColors();
  const r = document.documentElement;
  r.style.setProperty('--chart-color-primary', colors.accent);
  r.style.setProperty('--chart-color-secondary', colors.success);
  r.style.setProperty('--chart-color-warn', colors.warn);
  r.style.setProperty('--chart-color-danger', colors.danger);
  r.style.setProperty('--chart-bg', colors.card);
  r.style.setProperty('--chart-grid', colors.border);
  r.style.setProperty('--chart-font-family', theme.typography.fontBase);
}

// ECharts 공통 옵션 베이스 (각 차트가 deep-merge 해서 사용)
export function getEChartsBase() {
  const colors = getColors();
  return {
    backgroundColor: 'transparent',
    textStyle: {
      color: colors.text,
      fontFamily: theme.typography.fontBase,
    },
    tooltip: {
      backgroundColor: colors.card,
      borderColor: colors.border,
      textStyle: {
        color: colors.text,
        fontSize: 12,
      },
    },
    axisLineColor: colors.borderMuted,
    splitLineColor: colors.borderMuted,
    labelColor: colors.textDim,
  };
}

// Plotly layout 베이스 (P4 STOM Diagnostics 에서 dynamic import)
export function getPlotlyLayoutBase() {
  const colors = getColors();
  return {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: {
      color: colors.text,
      family: theme.typography.fontBase,
    },
    xaxis: { gridcolor: colors.borderMuted, linecolor: colors.border, tickcolor: colors.textDim },
    yaxis: { gridcolor: colors.borderMuted, linecolor: colors.border, tickcolor: colors.textDim },
  };
}
