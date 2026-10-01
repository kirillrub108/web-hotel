<script setup lang="ts">
import type { Service } from '~/types'

const { data: services, error } = await useFetch<Service[]>('/api/services', { key: 'services' })

const groups = computed(() => groupServices(services.value ?? []))

useHead({
  title: 'Услуги — Kivana',
  meta: [{ name: 'description', content: 'Услуги гостиницы Kivana: еда в номер, уборка, трансфер, SPA.' }],
})
</script>

<template>
  <section class="section">
    <div class="container">
      <h1>Услуги</h1>
      <p class="section__lead">
        Услуги и еду в номер можно заказать к подтверждённой брони в личном кабинете. Оплата — на ресепшене.
      </p>

      <p v-if="error" class="notice notice--error">Не удалось загрузить услуги. Обновите страницу через минуту.</p>

      <template v-else-if="groups.length">
        <div v-for="group in groups" :key="group.category" class="group">
          <h2>{{ group.title }}</h2>
          <div class="grid">
            <article v-for="service in group.services" :key="service.id" class="card service">
              <h3>{{ service.title }}</h3>
              <p class="service__text">{{ service.description }}</p>
              <p class="service__price">{{ servicePriceLabel(service) }}</p>
            </article>
          </div>
        </div>
      </template>

      <p v-else class="muted">Каталог услуг пока пуст.</p>
    </div>
  </section>
</template>

<style scoped>
.group {
  margin-top: var(--space-4);
}

.service {
  display: flex;
  flex-direction: column;
  padding: var(--space-3);
}

.service__text {
  color: var(--muted);
}

.service__price {
  margin: auto 0 0;
  font-weight: 700;
  color: var(--accent-dark);
}
</style>
