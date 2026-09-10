// Один и тот же относительный путь /api/... работает и в браузере, и при SSR:
// nitro проксирует его на backend, поэтому CORS в FastAPI не нужен.
const apiBase = process.env.API_BASE || 'http://localhost:8000'

export default defineNuxtConfig({
  compatibilityDate: '2025-09-01',
  devtools: { enabled: false },
  css: ['~/assets/css/main.css'],
  routeRules: {
    '/api/**': { proxy: `${apiBase}/api/**` },
  },
  // Bind-mount с Windows не отдаёт события inotify, без опроса dev-сервер не видит правок.
  vite: { server: { watch: { usePolling: true } } },
  watchers: { chokidar: { usePolling: true } },
})
