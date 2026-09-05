/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        slate: {
          950: '#07090e',
          900: '#0f141d',
          850: '#151c28',
          800: '#1b2434',
          700: '#2a364d',
        },
        emerald: {
          400: '#34d399',
          500: '#10b981',
          900: '#064e3b',
        },
        rose: {
          400: '#fb7185',
          500: '#f43f5e',
          900: '#881337',
        },
        indigo: {
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
        }
      },
    },
  },
  plugins: [],
}
