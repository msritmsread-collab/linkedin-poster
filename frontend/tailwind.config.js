/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      colors: {
        brand: {
          50:  '#FFF5F2',
          100: '#FFAC9C',
          200: '#FF9A86',
          300: '#FF7A63',
          400: '#F06E4E',
          500: '#E8613F',
          600: '#D05234',
          700: '#B03D22',
          800: '#9E1A00',
          900: '#7A1400',
        },
      },
    },
  },
  plugins: [],
}