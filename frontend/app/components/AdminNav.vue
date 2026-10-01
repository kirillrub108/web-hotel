<script setup lang="ts">
const route = useRoute()

const LINKS = [
  { to: '/admin', label: 'Заявки' },
  { to: '/admin/clients', label: 'Клиенты' },
  { to: '/admin/promos', label: 'Акции' },
]

// Заявки живут на /admin, остальные разделы — под своими префиксами; карточка клиента подсвечивает «Клиенты».
function isActive(to: string): boolean {
  return to === '/admin' ? route.path === '/admin' : route.path.startsWith(to)
}
</script>

<template>
  <nav class="admin-nav" aria-label="Разделы админки">
    <NuxtLink v-for="link in LINKS" :key="link.to" :to="link.to" :class="{ 'admin-nav__active': isActive(link.to) }">
      {{ link.label }}
    </NuxtLink>
  </nav>
</template>

<style scoped>
.admin-nav {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
  font-weight: 600;
}

.admin-nav a {
  color: var(--muted);
}

.admin-nav a.admin-nav__active {
  color: var(--accent-dark);
}
</style>
