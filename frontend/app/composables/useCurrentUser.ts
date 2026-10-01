import type { CurrentUser } from '~/types'

export function useCurrentUser() {
  const user = useState<CurrentUser | null>('current-user', () => null)
  // useRequestFetch при SSR пробрасывает cookie браузера в /api — так же, как это делает useFetch.
  const requestFetch = useRequestFetch()

  async function refresh(): Promise<void> {
    try {
      user.value = await requestFetch<CurrentUser>('/api/auth/me')
    }
    catch {
      // 401 — гость не вошёл; при недоступном API сайт тоже показываем как для гостя.
      user.value = null
    }
  }

  function clear(): void {
    user.value = null
  }

  // Один запрос /api/auth/me на открытие сайта: при SSR он выполняется на сервере,
  // результат приходит в браузер вместе со страницей. Дальше состояние меняют refresh() и clear().
  function load(): Promise<void> {
    return callOnce('current-user', refresh)
  }

  return { user, refresh, clear, load }
}
