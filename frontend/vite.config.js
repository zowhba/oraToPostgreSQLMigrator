import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // 스트리밍을 위해 프록시 버퍼링 비활성화 지원 (http-proxy 옵션)
        configure: (proxy, options) => {
          proxy.on('proxyRes', (proxyRes, req, res) => {
            // 백엔드의 SSE 헤더를 프론트엔드로 그대로 전달 보장
            proxyRes.headers['x-accel-buffering'] = 'no';
          });
        }
      }
    }
  }
})
