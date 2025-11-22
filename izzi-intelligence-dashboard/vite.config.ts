import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const basePath = process.env.VITE_BASE ?? '/'

// https://vite.dev/config/
export default defineConfig({
  base: basePath,
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: ['jota.ngrok.app', '.ngrok.app'],
  },
  preview: {
    host: true,
    allowedHosts: ['jota.ngrok.app', '.ngrok.app'],
  },
})
