import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: '#0b1220',
          panel: '#111c31',
          card: '#0f172a',
          hover: '#1e293b',
        },
        border: {
          DEFAULT: '#1e293b',
          subtle: '#16213a',
        },
        accent: {
          DEFAULT: '#38bdf8',
          muted: '#0ea5e9',
        },
        up: '#ef4444',
        down: '#22c55e',
        muted: '#64748b',
        subtle: '#94a3b8',
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
