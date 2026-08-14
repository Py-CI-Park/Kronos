import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import path from 'node:path';

// [B-2/REV-2] Vite base 는 Flask static_url_path='/static' 와 매핑된다.
// 빌드 산출물은 webui/static/v2/dist/ 에 위치하며, asset URL 은 /static/v2/dist/assets/...
const configuredOutDir = process.env.KRONOS_VITE_OUT_DIR;
const outDir = configuredOutDir
  ? path.resolve(configuredOutDir)
  : path.resolve(__dirname, '../static/v2/dist');

const normalizeChunkWhitespace = {
  name: 'normalize-chunk-whitespace',
  renderChunk(code: string) {
    return { code: code.replace(/[ \t]+$/gm, ''), map: null };
  },
};

export default defineConfig({
  base: '/static/v2/dist/',
  plugins: [svelte(), normalizeChunkWhitespace],
  build: {
    outDir,
    emptyOutDir: true,
    sourcemap: true,
    target: 'es2020',
    chunkSizeWarningLimit: 1400,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/echarts/') || id.includes('/node_modules/zrender/')) return 'vendor-echarts';
          if (id.includes('/node_modules/marked/') || id.includes('/node_modules/dompurify/')) return 'vendor-content';
          if (id.includes('/node_modules/svelte/')) return 'vendor-svelte';
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    // [REV-2] 학습 디렉터리는 watch 제외 — finetune outputs 의 jsonl append 가 dev HMR 을 폭주시키는 것을 차단
    watch: {
      ignored: [
        '**/finetune/outputs/**',
        '**/_database/**',
        '**/checkpoints/**',
        '**/logs/**',
        '**/webui/prediction_results/**',
        '**/webui/stom_predictions/**',
        '**/*.db',
      ],
    },
  },
  resolve: {
    alias: {
      $lib: path.resolve(__dirname, 'src/lib'),
      $widgets: path.resolve(__dirname, 'src/widgets'),
      $tabs: path.resolve(__dirname, 'src/tabs'),
      $layout: path.resolve(__dirname, 'src/layout'),
    },
  },
});
