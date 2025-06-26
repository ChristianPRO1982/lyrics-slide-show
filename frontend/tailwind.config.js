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
    'w-1/5',
    'w-1/6',
    'grid',
    'grid-cols-1',
    'grid-cols-2',
    'grid-cols-3',
    'grid-cols-4',
    'grid-cols-5',
    'grid-cols-6',
    'grid-cols-7',
    'grid-cols-8',
    'grid-cols-9',
    'grid-cols-10',
    'gap-2',
    'gap-4',
    'gap-6',
    'gap-8',
    'gap-10',
    'mt-1',
    'px-1',
    'w-4',
    'h-4',
    'sticky',
    'top-0',
    'h-36'
  ],
  theme: {
    extend: {},
  },
  plugins: [],
  corePlugins: {
    preflight: true, // normalement c’est true par défaut, mais mets-le pour être sûr
  },
};
