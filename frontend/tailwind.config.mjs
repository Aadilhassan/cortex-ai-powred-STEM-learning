/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        sp: {
          base: '#09090b',
          surface: '#18181b',
          elevated: '#27272a',
          border: '#3f3f46',
          'border-subtle': '#27272a',
          text: '#fafafa',
          body: '#d4d4d8',
          muted: '#71717a',
          accent: '#818cf8',
          'accent-hover': '#a5b4fc',
          'accent-glow': 'rgba(129, 140, 248, 0.2)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
