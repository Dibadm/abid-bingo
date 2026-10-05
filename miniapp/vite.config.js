import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Telegram's WebView loads the Mini App from whatever HTTPS URL is
// configured in config.MINI_APP_URL (bot.py / BotFather). Vite's default
// build output (dist/) with relative asset paths works correctly when
// served from the root of that domain - if you ever serve this from a
// sub-path (e.g. https://example.com/miniapp/), set base: '/miniapp/'
// below to match, or assets will 404 inside the Telegram WebView.
export default defineConfig({
  plugins: [react()],
  base: './',
  define: {
    'import.meta.env.VITE_BROADCAST_ENABLED': JSON.stringify(process.env.BROADCAST_ENABLED || 'false'),
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  server: {
    port: 5173,
    host: true,
    allowedHosts: ['all'],
  },
})
