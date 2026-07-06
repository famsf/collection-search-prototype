// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

// Served from GitHub Pages at https://famsf.github.io/collection-search-prototype/
// so both `site` and `base` are set; links + assets use import.meta.env.BASE_URL.
export default defineConfig({
  site: 'https://famsf.github.io',
  base: '/collection-search-prototype',
  vite: { plugins: [tailwindcss()] },
});
