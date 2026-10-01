<script setup lang="ts">
import type { Room } from '~/types'

const { clear } = useCurrentUser()

async function toLogin(): Promise<void> {
  clear()
  await navigateTo({ path: '/login', query: { next: '/admin/rooms' } })
}

const { data, error, refresh } = await useFetch<Room[]>('/api/admin/rooms')

if (error.value?.statusCode === 401) {
  await toLogin()
}

const editing = ref<Room | null>(null)

async function onSaved(): Promise<void> {
  editing.value = null
  await refresh()
}

useHead({
  title: 'Номера — Kivana',
  meta: [{ name: 'robots', content: 'noindex' }],
})
</script>

<template>
  <section class="section">
    <div class="container">
      <AdminNav />
      <h1>Номера</h1>
      <p class="muted lead">
        Здесь меняются цена, описание и доступность номера. Если снять номер с продажи, новые брони на него
        оформить нельзя, а уже оформленные заявки и подтверждённые брони не меняются. Цена в оформленных бронях
        тоже остаётся прежней. Фотографии номеров загрузить нельзя.
      </p>

      <p v-if="error && error.statusCode !== 401" class="notice notice--error">
        Не удалось загрузить номера. Обновите страницу через минуту.
      </p>

      <div v-else-if="data && data.length" class="card table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Номер</th>
              <th>Гостей</th>
              <th>Цена за ночь</th>
              <th>Описание</th>
              <th>Состояние</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="room in data" :key="room.id">
              <td>
                <strong>{{ room.name }}</strong><br>
                <span class="muted">{{ room.slug }}</span>
              </td>
              <td>{{ room.capacity }}</td>
              <td class="nowrap">{{ formatRubles(room.price_per_night) }}</td>
              <td class="description">{{ room.description }}</td>
              <td>{{ room.is_available ? 'Доступен' : 'Снят с продажи' }}</td>
              <td class="actions">
                <button class="link-button" type="button" @click="editing = room">Изменить</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="data" class="card empty">
        <p>Номеров пока нет.</p>
      </div>
    </div>

    <RoomFormDialog
      v-if="editing"
      :room="editing"
      @close="editing = null"
      @done="onSaved"
      @unauthorized="toLogin"
    />
  </section>
</template>

<style scoped>
.lead {
  margin: 0 0 var(--space-2);
  font-size: 0.92rem;
}

.description {
  max-width: 28rem;
  font-size: 0.9rem;
}
</style>
