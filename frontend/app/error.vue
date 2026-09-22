<script setup lang="ts">
import type { NuxtError } from '#app'

const props = defineProps<{ error: NuxtError }>()

const isNotFound = computed(() => props.error.statusCode === 404)

useHead({ title: (isNotFound.value ? 'Страница не найдена' : 'Ошибка') + ' — Тихая гавань' })
</script>

<template>
  <AppHeader />
  <main>
    <section class="section">
      <div class="container error">
        <p class="error__code">{{ error.statusCode }}</p>
        <h1>{{ isNotFound ? 'Такой страницы нет' : 'Что-то пошло не так' }}</h1>
        <p class="error__text">
          {{ isNotFound
            ? 'Возможно, ссылка устарела или номер больше не сдаётся.'
            : 'Сайт временно недоступен. Попробуйте обновить страницу через минуту или позвоните нам.' }}
        </p>
        <button class="button" type="button" @click="clearError({ redirect: '/rooms' })">
          Посмотреть номера
        </button>
      </div>
    </section>
  </main>
  <AppFooter />
</template>

<style scoped>
.error {
  text-align: center;
}

.error__code {
  color: var(--accent);
  font-size: 4rem;
  font-weight: 700;
  line-height: 1;
}

.error__text {
  color: var(--muted);
  max-width: 46ch;
  margin: 0 auto var(--space-3);
}
</style>
