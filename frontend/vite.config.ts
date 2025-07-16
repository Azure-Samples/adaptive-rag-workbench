import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5175,
    // Commenting out proxy to use direct API calls to Azure backend
    // proxy: {
    //   '/api': {
    //     target: process.env.VITE_PROXY_TARGET || 'http://localhost:8002',
    //     changeOrigin: true,
    //   },
    // },
  },
})

