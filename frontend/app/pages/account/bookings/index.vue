<script setup lang="ts">
import type { Booking } from '~/types'

const { data: bookings, error } = await useFetch<Booking[]>('/api/account/bookings')

useHead({ title: 'Мои брони — Kivana', meta: [{ name: 'robots', content: 'noindex' }] })
</script>

<template>
  <section class="section">
    <div class="container">
      <AccountNav />
      <h1>Мои брони</h1>

      <p v-if="error" class="notice notice--error">Не удалось загрузить брони. Обновите страницу через минуту.</p>

      <div v-else-if="bookings && bookings.length" class="list">
        <NuxtLink v-for="item in bookings" :key="item.id" class="card item" :to="`/account/bookings/${item.id}`">
          <div>
            <p class="item__room">{{ item.room.name }}</p>
            <p class="item__dates">
              {{ formatDate(item.check_in) }} — {{ formatDate(item.check_out) }} · {{ nightsLabel(item.nights) }}
            </p>
          </div>
          <div class="item__side">
            <StatusBadge :status="item.display_status" />
            <span class="item__price">{{ formatRubles(item.total_price) }}</span>
          </div>
        </NuxtLink>
      </div>

      <div v-else-if="bookings" class="card empty">
        <p>Броней пока нет.</p>
        <NuxtLink class="button" to="/rooms">Выбрать номер</NuxtLink>
      </div>
    </div>
  </section>
</template>

<style scoped>
.list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  color: var(--text);
}

.item p {
  margin: 0;
}

.item__room {
  font-weight: 600;
}

.item__dates {
  color: var(--muted);
  font-size: 0.92rem;
}

.item__side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.item__price {
  font-weight: 600;
  white-space: nowrap;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3);
}

.empty p {
  margin: 0;
}
</style>
