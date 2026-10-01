<script setup lang="ts">
const route = useRoute()

const LINKS = [
  { to: '/admin', label: 'Заявки' },
  { to: '/admin/clients', label: 'Клиенты' },
  { to: '/admin/rooms', label: 'Номера' },
  { to: '/admin/promos', label: 'Акции' },
  { to: '/admin/services', label: 'Услуги' },
  { to: '/admin/service-orders', label: 'Заказы услуг' },
  { to: '/admin/housekeeping', label: 'Уборка' },
]

// Заявки живут на /admin, остальные разделы — под своими префиксами; карточка клиента подсвечивает «Клиенты».
function isActive(to: string): boolean {
  return to === '/admin' ? route.path === '/admin' : route.path.startsWith(to)
}

// На телефоне разделы — лента с прокруткой: активный пункт подводим в видимую область.
const nav = ref<HTMLElement | null>(null)
onMounted(() => {
  nav.value?.querySelector<HTMLElement>('.subnav__link--active')?.scrollIntoView({ inline: 'center', block: 'nearest' })
})
</script>

<template>
  <nav ref="nav" class="subnav subnav--scroll" aria-label="Разделы админки">
    <NuxtLink v-for="link in LINKS" :key="link.to" :to="link.to" :class="{ 'subnav__link--active': isActive(link.to) }">
      {{ link.label }}
    </NuxtLink>
  </nav>
</template>
