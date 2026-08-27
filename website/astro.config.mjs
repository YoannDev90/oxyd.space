// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
  site: 'https://oxyd.space',
  output: 'static',
  build: {
    format: 'directory'
  },
  outDir: '../dist',
  publicDir: './public',
  srcDir: './src'
});
