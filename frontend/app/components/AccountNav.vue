<script setup lang="ts">
const { user } = useCurrentUser()
const route = useRoute()
// Список и страница брони — соседние маршруты, поэтому подсветка раздела считается по префиксу пути.
const inBookings = computed(() => route.path.startsWith('/account/bookings'))
</script>

<template>
  <nav class="subnav account-nav" aria-label="Личный кабинет">
    <NuxtLink to="/account" exact-active-class="subnav__link--active">Обзор</NuxtLink>
    <NuxtLink to="/account/bookings" :class="{ 'subnav__link--active': inBookings }">Мои брони</NuxtLink>
    <NuxtLink to="/account/profile" exact-active-class="subnav__link--active">Профиль</NuxtLink>
    <NuxtLink v-if="user?.role === 'admin'" to="/admin">Админка</NuxtLink>
  </nav>
</template>

<style scoped>
.account-nav {
  margin-bottom: var(--space-3);
}
</style>
