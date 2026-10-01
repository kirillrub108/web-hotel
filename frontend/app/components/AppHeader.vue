<script setup lang="ts">
const isMenuOpen = ref(false)
const { user } = useCurrentUser()
</script>

<template>
  <header class="header" @keydown.esc="isMenuOpen = false">
    <div class="container header__inner">
      <NuxtLink to="/" class="header__logo" @click="isMenuOpen = false">
        Kivana
      </NuxtLink>

      <button
        class="header__toggle"
        type="button"
        aria-controls="site-nav"
        :aria-expanded="isMenuOpen"
        aria-label="Меню"
        @click="isMenuOpen = !isMenuOpen"
      >
        {{ isMenuOpen ? '✕' : '☰' }}
      </button>

      <nav id="site-nav" class="header__nav" :class="{ 'header__nav--open': isMenuOpen }" aria-label="Основное меню">
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
/* Телефон: пункты меню прячутся за бургером и раскрываются списком под шапкой. */
.header {
  position: sticky;
  top: 0;
  z-index: 10;
  padding-top: var(--safe-top);
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}

.header__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0 var(--space-2);
  padding-top: 6px;
  padding-bottom: 6px;
}

.header__logo {
  display: inline-flex;
  align-items: center;
  min-height: var(--tap);
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--tap);
  height: var(--tap);
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-size: 1.2rem;
  cursor: pointer;
}

.header__nav {
  display: none;
  width: 100%;
  flex-direction: column;
  max-height: calc(100dvh - var(--safe-top) - 64px);
  overflow-y: auto;
  padding-bottom: var(--space-1);
}

.header__nav--open {
  display: flex;
}

.header__nav a {
  display: flex;
  align-items: center;
  min-height: var(--tap);
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-weight: 600;
}

.header__nav a:hover,
.header__nav a.router-link-active {
  color: var(--accent-dark);
  text-decoration: none;
}

@media (min-width: 640px) {
  .header__toggle {
    display: none;
  }

  .header__nav {
    display: flex;
    width: auto;
    flex-direction: row;
    gap: var(--space-2);
    max-height: none;
    overflow: visible;
    padding-bottom: 0;
  }

  .header__nav a {
    border-top: 0;
  }
}

@media (min-width: 1024px) and (pointer: fine) {
  .header__inner {
    padding-top: var(--space-2);
    padding-bottom: var(--space-2);
  }

  .header__logo,
  .header__nav a {
    min-height: 0;
  }
}

@media (min-width: 1024px) {
  .header__nav {
    gap: var(--space-3);
  }
}
</style>
