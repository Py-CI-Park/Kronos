/** @type {import('tailwindcss').Config} */
// [AC-1] Tailwind prebuilt 강제 — Play CDN 사용 금지
export default {
  content: ['./index.html', './src/**/*.{svelte,ts,js}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // design_spec §2.2 디자인 토큰과 일치
        bg: '#0f172a',
        card: '#111827',
        'card-raised': '#0b1120',
        border: '#243244',
        'border-muted': '#1e293b',
        text: '#e2e8f0',
        'text-muted': '#94a3b8',
        'text-dim': '#64748b',
        'text-faint': '#475569',
        accent: '#38bdf8',
        'accent-subtle': '#bfdbfe',
        success: '#22c55e',
        'success-bg': '#14532d',
        warn: '#f59e0b',
        'warn-bg': '#422006',
        danger: '#ef4444',
        info: '#93c5fd',
        'info-bg': '#0c4a6e',
      },
      fontFamily: {
        sans: ["'Segoe UI'", "'Malgun Gothic'", 'sans-serif'],
        mono: ["'Consolas'", "'D2Coding'", 'monospace'],
      },
      borderRadius: {
        md: '10px',
        lg: '14px',
      },
      boxShadow: {
        sm: '0 1px 3px rgba(0,0,0,.4)',
        md: '0 4px 12px rgba(0,0,0,.5)',
        lg: '0 8px 24px rgba(0,0,0,.6)',
        xl: '0 16px 40px rgba(0,0,0,.7)',
      },
      transitionDuration: {
        fast: '100ms',
        base: '150ms',
        slow: '400ms',
      },
    },
  },
  plugins: [],
};
