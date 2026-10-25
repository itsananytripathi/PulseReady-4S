import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0B0F19',
        paper: '#0B0F19',
        nav: '#111827',
        panel: '#151E2E',
        raised: '#1D293B',
        line: '#29364B',
        muted: '#8495AF',
        cyan: '#00D5F2',
        teal: '#10C997',
        amber: '#F5A524',
        danger: '#F04452',
      },
      boxShadow: { panel: '0 12px 32px rgba(0, 0, 0, 0.18)' },
    },
  },
  plugins: [],
} satisfies Config
