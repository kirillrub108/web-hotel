<script setup lang="ts">
await useCurrentUser().load()
</script>

<template>
  <AppHeader />
  <main>
    <NuxtPage />
  </main>
  <AppFooter />
</template>

<style>
/* Подвал прижат к низу экрана и на коротких страницах (вход, пустой список). */
#__nuxt {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-height: 100dvh;
}

main {
  flex: 1 0 auto;
  min-height: 60vh;
}
</style>
