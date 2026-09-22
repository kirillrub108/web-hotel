<script setup lang="ts">
import type { Room } from '~/types'

const capacity = ref(0)
const maxPrice = ref(0)

const query = computed(() => ({
  ...(capacity.value ? { capacity: capacity.value } : {}),
  ...(maxPrice.value ? { max_price: maxPrice.value } : {}),
}))

const { data: rooms, status, error } = await useFetch<Room[]>('/api/rooms', { query })

const hasFilters = computed(() => capacity.value > 0 || maxPrice.value > 0)

function reset(): void {
  capacity.value = 0
  maxPrice.value = 0
}

useHead({ title: 'Номера — Тихая гавань' })
</script>

<template>
  <section class="section">
    <div class="container">
      <h1>Номера</h1>
      <p class="section__lead">
        Шесть категорий: от компактного эконома до двухуровневых апартаментов.
        Цена указана за ночь и включает завтрак.
      </p>

      <form class="filters card" @submit.prevent>
        <div class="field">
          <label for="capacity">Гостей в номере</label>
          <select id="capacity" v-model.number="capacity">
            <option :value="0">Любое количество</option>
            <option :value="1">от 1</option>
            <option :value="2">от 2</option>
            <option :value="3">от 3</option>
            <option :value="4">от 4</option>
            <option :value="5">от 5</option>
          </select>
        </div>

        <div class="field">
          <label for="max_price">Цена за ночь</label>
          <select id="max_price" v-model.number="maxPrice">
            <option :value="0">Любая цена</option>
            <option :value="3000">до 3 000 ₽</option>
            <option :value="5000">до 5 000 ₽</option>
            <option :value="7000">до 7 000 ₽</option>
            <option :value="10000">до 10 000 ₽</option>
            <option :value="15000">до 15 000 ₽</option>
          </select>
        </div>

        <button v-if="hasFilters" class="button button--ghost filters__reset" type="button" @click="reset">
          Сбросить
        </button>
      </form>

      <p v-if="status === 'pending'" class="hint">Подбираем номера…</p>

      <p v-else-if="error" class="notice notice--error">
        Не удалось загрузить номера. Обновите страницу через минуту или позвоните нам.
      </p>

      <div v-else-if="rooms && rooms.length" class="grid">
        <RoomCard v-for="room in rooms" :key="room.id" :room="room" />
      </div>

      <div v-else class="card empty">
        <h3>Ничего не найдено</h3>
        <p>Под выбранные условия нет ни одного номера. Попробуйте увеличить бюджет или уменьшить число гостей.</p>
        <button class="button" type="button" @click="reset">Показать все номера</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.filters {
  display: flex;
  gap: var(--space-3);
  align-items: end;
  flex-wrap: wrap;
  padding: var(--space-3);
  margin-bottom: var(--space-4);
}

.filters select {
  min-width: 200px;
  padding: 11px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font: inherit;
}

.filters__reset {
  padding: 11px 22px;
}

.hint {
  color: var(--muted);
}

.empty {
  padding: var(--space-4);
  text-align: center;
}

.empty p {
  color: var(--muted);
  max-width: 46ch;
  margin: 0 auto var(--space-3);
}
</style>
