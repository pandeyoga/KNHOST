/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    extend: {
      // FIX-4 — Standar UI Gudang v1 (docs/KN_37_STANDAR_UI_GUDANG.md, K-B4-02/03). Kode baru memakai kelas ini
      // (`text-fs-14`, `text-kn-text-2`, `bg-kn-action`…) — bukan `text-[11px]`/`text-[#8E8E93]` (ratchet G-UI-01/02).
      fontSize: {
        'fs-12': ['12px', '16px'],
        'fs-13': ['13px', '18px'],
        'fs-14': ['14px', '20px'],
        'fs-16': ['16px', '24px'],
        'fs-20': ['20px', '28px'],
        'fs-24': ['24px', '32px'],
        'fs-kiosk-40': ['40px', '48px'],
        'fs-kiosk-64': ['64px', '72px'],
      },
      minHeight: { touch: '48px', 'touch-primary': '56px' },
      minWidth: { touch: '48px' },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)'
      },
      colors: {
        kn: {
          text: 'var(--kn-text)', 'text-2': 'var(--kn-text-2)', neutral: 'var(--kn-neutral)',
          'neutral-soft': 'var(--kn-neutral-soft)', action: 'var(--kn-action)', 'action-soft': 'var(--kn-action-soft)',
          'success-text': 'var(--kn-success-text)', 'success-solid': 'var(--kn-success-solid)',
          'success-soft': 'var(--kn-success-soft)', 'warning-text': 'var(--kn-warning-text)',
          'warning-soft': 'var(--kn-warning-soft)', 'danger-text': 'var(--kn-danger-text)', danger: 'var(--kn-danger)',
          'danger-soft': 'var(--kn-danger-soft)', 'special-text': 'var(--kn-special-text)',
          'special-soft': 'var(--kn-special-soft)', 'field-border': 'var(--kn-field-border)', divider: 'var(--kn-divider)',
        },
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))'
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))'
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))'
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))'
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))'
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))'
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))'
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        chart: {
          '1': 'hsl(var(--chart-1))',
          '2': 'hsl(var(--chart-2))',
          '3': 'hsl(var(--chart-3))',
          '4': 'hsl(var(--chart-4))',
          '5': 'hsl(var(--chart-5))'
        }
      },
      keyframes: {
        'accordion-down': {
          from: {
            height: '0'
          },
          to: {
            height: 'var(--radix-accordion-content-height)'
          }
        },
        'accordion-up': {
          from: {
            height: 'var(--radix-accordion-content-height)'
          },
          to: {
            height: '0'
          }
        }
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out'
      }
    }
  },
  plugins: [require("tailwindcss-animate")],
};