function inSection(path: string, section: string): boolean {
  return path === section || path.startsWith(`${section}/`)
}

// Закрытые разделы: /account — для вошедших, /admin — только для администратора.
// Проверка идёт до отрисовки страницы, поэтому при SSR браузер сразу получает редирект без мигания.
export default defineNuxtRouteMiddleware(async (to) => {
  const isAdminArea = inSection(to.path, '/admin')
  if (!isAdminArea && !inSection(to.path, '/account')) {
    return
  }

  const { user, load } = useCurrentUser()
  await load()
  if (!user.value) {
    return navigateTo({ path: '/login', query: { next: to.fullPath } })
  }
  if (isAdminArea && user.value.role !== 'admin') {
    return navigateTo('/account')
  }
})
