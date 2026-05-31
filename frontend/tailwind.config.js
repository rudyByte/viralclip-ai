/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Outfit', 'Inter', 'sans-serif'],
      },
      colors: {
        brand: {
          50:  '#f0f4ff',
          100: '#e0e9ff',
          200: '#c7d7fe',
          300: '#a5b8fd',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
        },
        accent: {
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
        },
        neon: {
          pink:   '#f472b6',
          purple: '#a855f7',
          blue:   '#38bdf8',
          green:  '#4ade80',
        },
        surface: {
          900: '#0a0a0f',
          800: '#0f0f1a',
          700: '#141424',
          600: '#1a1a2e',
          500: '#1e1e35',
          400: '#252540',
        },
      },
      backgroundImage: {
        'gradient-brand': 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%)',
        'gradient-glow':  'linear-gradient(135deg, #4338ca 0%, #6d28d9 100%)',
        'gradient-dark':  'linear-gradient(180deg, #0f0f1a 0%, #0a0a0f 100%)',
        'gradient-card':  'linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(139,92,246,0.04) 100%)',
        'gradient-viral': 'linear-gradient(90deg, #f472b6, #a855f7, #38bdf8)',
      },
      animation: {
        'pulse-slow':    'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow':          'glow 2s ease-in-out infinite alternate',
        'float':         'float 6s ease-in-out infinite',
        'slide-up':      'slideUp 0.5s ease-out',
        'fade-in':       'fadeIn 0.4s ease-out',
        'shimmer':       'shimmer 2s linear infinite',
        'spin-slow':     'spin 8s linear infinite',
        'bounce-subtle': 'bounceSubtle 1s ease-in-out infinite',
      },
      keyframes: {
        glow: {
          '0%':   { boxShadow: '0 0 20px rgba(99,102,241,0.3)' },
          '100%': { boxShadow: '0 0 40px rgba(139,92,246,0.6), 0 0 80px rgba(99,102,241,0.2)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%':      { transform: 'translateY(-12px)' },
        },
        slideUp: {
          '0%':   { opacity: 0, transform: 'translateY(20px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%':   { opacity: 0 },
          '100%': { opacity: 1 },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-1000px 0' },
          '100%': { backgroundPosition: '1000px 0' },
        },
        bounceSubtle: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%':      { transform: 'translateY(-4px)' },
        },
      },
      boxShadow: {
        'brand':    '0 0 30px rgba(99,102,241,0.3)',
        'brand-lg': '0 0 60px rgba(99,102,241,0.4), 0 0 120px rgba(139,92,246,0.2)',
        'card':     '0 4px 24px rgba(0,0,0,0.4), 0 1px 4px rgba(0,0,0,0.3)',
        'neon':     '0 0 20px rgba(168,85,247,0.5)',
        'glow-sm':  '0 2px 12px rgba(99,102,241,0.4)',
      },
    },
  },
  plugins: [],
}
