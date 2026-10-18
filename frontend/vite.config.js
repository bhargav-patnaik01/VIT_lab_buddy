import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: the UI runs on :5173 and proxies /api to the local FastAPI server on :8000.
// Production (AWS): CloudFront serves this build from S3 and routes /api/* to API Gateway, so the same relative URLs work.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: { sourcemap: false, chunkSizeWarningLimit: 700 },
})
