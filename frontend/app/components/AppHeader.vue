<script setup lang="ts">
const isMenuOpen = ref(false)
const { user } = useCurrentUser()
</script>

<template>
  <header class="header">
    <div class="container header__inner">
      <NuxtLink to="/" class="header__logo" @click="isMenuOpen = false">
        Kivana
      </NuxtLink>

      <button
        class="header__toggle"
        type="button"
        :aria-expanded="isMenuOpen"
        aria-label="Меню"
        @click="isMenuOpen = !isMenuOpen"
      >
        ☰
      </button>

      <nav class="header__nav" :class="{ 'header__nav--open': isMenuOpen }">
        <NuxtLink to="/" @click="isMenuOpen = false">Главная</NuxtLink>
        <NuxtLink to="/rooms" @click="isMenuOpen = false">Номера</NuxtLink>
        <NuxtLink to="/services" @click="isMenuOpen = false">Услуги</NuxtLink>
        <NuxtLink to="/contacts" @click="isMenuOpen = false">Контакты</NuxtLink>
        <NuxtLink v-if="user?.role === 'admin'" to="/admin" @click="isMenuOpen = false">Админка</NuxtLink>
        <NuxtLink v-if="user" to="/account" @click="isMenuOpen = false">Кабинет</NuxtLink>
        <NuxtLink v-else to="/login" @click="isMenuOpen = false">Войти</NuxtLink>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}

.header__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding-top: var(--space-2);
  padding-bottom: var(--space-2);
}

.header__logo {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text);
  letter-spacing: 0.02em;
}

.header__logo:hover {
  text-decoration: none;
  color: var(--accent-dark);
}

.header__toggle {
  display: none;
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 1.2rem;
  cursor: pointer;
}

.header__nav {
  display: flex;
  gap: var(--space-3);
}

.header__nav a {
  color: var(--muted);
  font-weight: 600;
}

.header__nav a:hover,
.header__nav a.router-link-active {
  color: var(--accent-dark);
  text-decoration: none;
}

@media (max-width: 700px) {
  .header__toggle {
    display: block;
  }

  .header__nav {
    display: none;
    width: 100%;
    flex-direction: column;
    gap: var(--space-1);
    padding-bottom: var(--space-1);
  }

  .header__nav--open {
    display: flex;
  }
}
</style>
