// Один и тот же относительный путь /api/... работает и в браузере, и при SSR:
// nitro проксирует его на backend, поэтому CORS в FastAPI не нужен.
const apiBase = process.env.API_BASE || 'http://localhost:8000'
// Bind-mount с Windows не отдаёт события inotify, поэтому в Docker включён опрос файлов.
const usePolling = process.env.WATCH_POLLING === 'true'

export default defineNuxtConfig({
  compatibilityDate: '2025-09-01',
  devtools: { enabled: false },
  css: ['~/assets/css/main.css'],
  app: {
    head: {
      htmlAttrs: { lang: 'ru' },
      meta: [
        { name: 'description', content: 'Гостиница Kivana в центре Ярославля: номера от эконома до апартаментов, завтрак, парковка.' },
      ],
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }],
    },
  },
  runtimeConfig: {
    // Переопределяется переменной NUXT_PUBLIC_PASSWORD_MIN_LENGTH — в compose она берётся из PASSWORD_MIN_LENGTH backend.
    public: { passwordMinLength: 15 },
  },
  routeRules: {
    '/api/**': { proxy: `${apiBase}/api/**` },
  },
  vite: { server: { watch: { usePolling } } },
  watchers: { chokidar: { usePolling } },
})
