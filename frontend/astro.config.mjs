// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import node from '@astrojs/node';

// https://astro.build/config
export default defineConfig({
  output: 'server',
  adapter: node({ mode: 'standalone' }),
  integrations: [react()],
  server: { port: 4321 },
  vite: {
    server: {
      proxy: {
        '/api': 'http://localhost:8000',
        '/ws': { target: 'ws://localhost:8000', ws: true },
      }
    }
  }
});
