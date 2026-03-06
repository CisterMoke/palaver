import { defineConfig, loadEnv } from 'vite'
import preact from '@preact/preset-vite'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path';

// https://vite.dev/config/
export default defineConfig(({ mode }: { mode: string }) => {
  process.env = {...process.env, ...loadEnv(mode, resolve(__dirname, '../../'), '')}
  return {
    plugins: [
      preact(),
      tailwindcss(),
    ],
    envDir: "../",
    define: {
      'import.meta.env.PALAVER_API_HOST': JSON.stringify(process.env.PALAVER_API_HOST),
      'import.meta.env.PALAVER_API_PORT': JSON.stringify(process.env.PALAVER_API_PORT),
    },
  };
});