/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#090d16',
        surface: {
          DEFAULT: '#0f172a',
          raised: '#1e293b',
          hover: '#334155',
        },
        border: {
          subtle: '#1e293b',
          DEFAULT: '#334155',
          strong: '#475569',
        },
        text: {
          primary: '#f8fafc',
          secondary: '#94a3b8',
          muted: '#64748b',
          disabled: '#475569',
        },
        primary: {
          500: '#3b82f6',
          600: '#2563eb',
          hover: '#1d4ed8',
        },
        status: {
          completed: {
            fg: '#10b981',
            bg: 'rgba(16, 185, 129, 0.12)',
            border: 'rgba(16, 185, 129, 0.28)',
          },
          running: {
            fg: '#38bdf8',
            bg: 'rgba(56, 189, 248, 0.12)',
            border: 'rgba(56, 189, 248, 0.32)',
          },
          failed: {
            fg: '#f43f5e',
            bg: 'rgba(244, 63, 94, 0.12)',
            border: 'rgba(244, 63, 94, 0.32)',
          },
          interrupted: {
            fg: '#f59e0b',
            bg: 'rgba(245, 158, 11, 0.12)',
            border: 'rgba(245, 158, 11, 0.32)',
          },
          cancelled: {
            fg: '#94a3b8',
            bg: 'rgba(148, 163, 184, 0.10)',
            border: 'rgba(148, 163, 184, 0.25)',
          },
        },
        unavailable: '#64748b',
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
        mono: [
          'JetBrains Mono',
          'Fira Code',
          'ui-monospace',
          'SFMono-Regular',
          'monospace',
        ],
      },
      keyframes: {
        pulseDot: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.35' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        spin: {
          to: { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        pulseDot: 'pulseDot 1.4s ease-in-out infinite',
        shimmer: 'shimmer 1.5s infinite',
        fadeIn: 'fadeIn 200ms ease-out',
        slideUp: 'slideUp 240ms ease-out',
        spin: 'spin 0.7s linear infinite',
      },
    },
  },
  plugins: [],
};
