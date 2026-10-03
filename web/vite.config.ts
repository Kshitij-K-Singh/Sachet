// From vitest/config, not vite: that re-export knows the `test` block, so the
// Vite config and the Vitest config stay one file.
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  preview: {
    // vite preview rejects Host headers it does not know (HTTP 403
    // "not allowed"). The deployed domain must be listed here or the
    // Railway URL serves nothing. Localhost stays for `npm run preview`.
    // If the Railway domain changes, update this list and redeploy.
    allowedHosts: [
      "localhost",
      "127.0.0.1",
      "web-production-cde2c.up.railway.app",
    ],
  },
  test: {
    // The tab-capture hook touches navigator.mediaDevices, MediaRecorder,
    // AudioContext and DOMException, none of which exist in node.
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
})
