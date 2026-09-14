/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        hud: {
          bg: '#070b12',
          surface: '#0d1527',
          card: '#121e36',
          panel: '#162340',
          border: '#1f3154',
          'border-light': '#2b4474',
          accent: '#06b6d4',
          cyan: '#00f0ff',
          emerald: '#10b981',
          crimson: '#ef4444',
          amber: '#f59e0b',
          muted: '#94a3b8',
        }
      },
      fontFamily: {
        sans: ['Outfit', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'laser-glow': 'laserGlow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        laserGlow: {
          '0%': { opacity: '0.4', filter: 'drop-shadow(0 0 4px #06b6d4)' },
          '100%': { opacity: '1', filter: 'drop-shadow(0 0 12px #00f0ff)' },
        }
      }
    },
  },
  plugins: [],
}
