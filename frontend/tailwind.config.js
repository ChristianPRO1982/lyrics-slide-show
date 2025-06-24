/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
    './static/**/*.html',
  ],
  safelist: [
    'w-1/2',
    'w-1/3',
    'w-1/4',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
  corePlugins: {
    preflight: true, // normalement c’est true par défaut, mais mets-le pour être sûr
  },
};
