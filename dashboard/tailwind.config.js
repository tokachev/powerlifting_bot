/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bucket: {
          squat: '#3b82f6',
          bench: '#ef4444',
          deadlift: '#22c55e',
          other: '#6b7280',
        },
      },
    },
  },
  plugins: [],
}
