// Rebuild CSS after changing templates:  npx tailwindcss@3 -c tailwind.config.js -i tw-input.css -o static/assets/css/tailwind.css --minify
// XPRISM palette, taken from the logo. The "teal" scale is remapped to XPRISM purple so every existing
// accent (buttons, tabs, badges, focus rings) follows the brand; dark slates become XPRISM navy.
const purple = { 50: '#faf3fe', 100: '#f2e2fc', 200: '#e5c6f9', 300: '#d29cf3', 400: '#b866ea', 500: '#9b33d9',
                 600: '#7e13b5', 700: '#681197', 800: '#55117a', 900: '#461264', 950: '#2d0442' };
module.exports = {
  content: ['./templates/**/*.html', './experiments/*.html', './static/assets/js/*.js', './lab/**/*.py'],
  theme: {
    extend: {
      colors: {
        teal: purple,
        slate: { 800: '#13294f', 900: '#0a1f44', 950: '#061430' },
        brand: { navy: '#08193b', purple: '#7e13b5', violet: '#4e1c8f', blue: '#066eaa', teal: '#2bbfb0' },
      },
      fontFamily: { display: ['Poppins', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'] },
    },
  },
  plugins: [],
};
