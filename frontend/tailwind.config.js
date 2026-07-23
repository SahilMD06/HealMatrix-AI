/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    container: {
      center: true,
      padding: '1.5rem',
      screens: { '2xl': '1440px' },
    },
    extend: {
      colors: {
        // Semantic tokens resolve to CSS variables so one class works in both themes.
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        // Brand accent ramp used for gradients, glows and highlights.
        brand: {
          indigo: '#6366f1',
          blue: '#3b82f6',
          electric: '#2563eb',
          purple: '#8b5cf6',
          cyan: '#06b6d4',
          emerald: '#10b981',
        },
        // Domain palette — triage acuity and sustainability status.
        triage: {
          1: '#f43f5e',
          2: '#fb923c',
          3: '#facc15',
          4: '#22c55e',
          5: '#22d3ee',
        },
        sustain: {
          excellent: '#10b981',
          good: '#84cc16',
          fair: '#f59e0b',
          poor: '#f43f5e',
        },
      },
      borderRadius: {
        xl: 'calc(var(--radius) + 4px)',
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: ['Inter', 'SF Pro Display', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glass: '0 8px 32px 0 rgba(2, 6, 23, 0.24)',
        elevated: '0 1px 2px rgba(2,6,23,.4), 0 12px 32px -8px rgba(2,6,23,.5)',
        glow: '0 0 0 1px rgba(99,102,241,.25), 0 8px 40px -8px rgba(99,102,241,.45)',
        'glow-cyan': '0 0 0 1px rgba(6,182,212,.25), 0 8px 40px -8px rgba(6,182,212,.4)',
        'glow-emerald': '0 0 0 1px rgba(16,185,129,.25), 0 8px 40px -8px rgba(16,185,129,.4)',
        'inner-top': 'inset 0 1px 0 0 rgba(255,255,255,.06)',
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #6366f1 0%, #3b82f6 45%, #06b6d4 100%)',
        'brand-radial': 'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99,102,241,.25), transparent)',
        'card-sheen': 'linear-gradient(180deg, rgba(255,255,255,.04), transparent 40%)',
      },
      keyframes: {
        'accordion-down': { from: { height: '0' }, to: { height: 'var(--radix-accordion-content-height)' } },
        'accordion-up': { from: { height: 'var(--radix-accordion-content-height)' }, to: { height: '0' } },
        shimmer: { '100%': { transform: 'translateX(100%)' } },
        'pulse-ring': {
          '0%': { transform: 'scale(0.85)', opacity: '0.7' },
          '70%': { transform: 'scale(1.7)', opacity: '0' },
          '100%': { transform: 'scale(1.7)', opacity: '0' },
        },
        'gradient-pan': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        'glow-pulse': {
          '0%, 100%': { opacity: '0.5' },
          '50%': { opacity: '1' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        shimmer: 'shimmer 1.6s infinite',
        'pulse-ring': 'pulse-ring 1.8s cubic-bezier(0.24, 0, 0.38, 1) infinite',
        'gradient-pan': 'gradient-pan 6s ease infinite',
        float: 'float 6s ease-in-out infinite',
        'glow-pulse': 'glow-pulse 2.4s ease-in-out infinite',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
}
