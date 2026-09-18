/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        gov: {
          navy: '#0f172a',       // Slate 900
          navyLight: '#1e293b',  // Slate 800
          blue: '#1d4ed8',       // Blue 700
          blueLight: '#eff6ff',  // Blue 50
          amber: '#d97706',      // Amber 600 (Saffron subtle accent)
          saffron: '#ea580c',    // Orange 600
          grayBg: '#f8fafc',     // Slate 50 background
          cardBg: '#ffffff',
          border: '#e2e8f0',
        },
        risk: {
          normalBg: '#ecfdf5',
          normalText: '#047857',
          normalBorder: '#a7f3d0',
          watchlistBg: '#fefce8',
          watchlistText: '#a16207',
          watchlistBorder: '#fef08a',
          highBg: '#fff7ed',
          highText: '#c2410c',
          highBorder: '#ffedd5',
          criticalBg: '#fef2f2',
          criticalText: '#b91c1c',
          criticalBorder: '#fecaca',
        }
      }
    },
  },
  plugins: [],
}
