<script setup lang="ts">
const { user } = useCurrentUser()
</script>

<template>
  <nav class="account-nav" aria-label="Личный кабинет">
    <NuxtLink to="/account" exact-active-class="account-nav__active">Обзор</NuxtLink>
    <NuxtLink to="/account/profile" exact-active-class="account-nav__active">Профиль</NuxtLink>
    <NuxtLink v-if="user?.role === 'admin'" to="/admin">Админка</NuxtLink>
  </nav>
</template>

<style scoped>
.account-nav {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  font-weight: 600;
}

.account-nav a {
  color: var(--muted);
}

.account-nav a.account-nav__active {
  color: var(--accent-dark);
}
</style>
