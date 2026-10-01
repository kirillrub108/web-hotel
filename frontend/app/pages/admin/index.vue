<script setup lang="ts">
import type { AdminBookingPage, BookingStatus } from '~/types'

const PAGE_SIZE = 20

const statusLabels: Record<BookingStatus, string> = {
  new: 'Новая',
  confirmed: 'Подтверждена',
  cancelled: 'Отменена',
}

const statusFilter = ref<BookingStatus | ''>('')
const page = ref(0)

watch(statusFilter, () => {
  page.value = 0
})

const query = computed(() => ({
  limit: PAGE_SIZE,
  offset: page.value * PAGE_SIZE,
  ...(statusFilter.value ? { status: statusFilter.value } : {}),
}))

const { data, error, refresh } = await useFetch<AdminBookingPage>('/api/admin/bookings', { query })

if (error.value?.statusCode === 401) {
  await navigateTo('/admin/login')
}

const total = computed(() => data.value?.total ?? 0)
const hasNextPage = computed(() => (page.value + 1) * PAGE_SIZE < total.value)

const actionError = ref('')
const busyId = ref<number | null>(null)

async function setStatus(id: number, status: BookingStatus): Promise<void> {
  actionError.value = ''
  busyId.value = id
  try {
    await $fetch(`/api/admin/bookings/${id}`, { method: 'PATCH', body: { status } })
    await refresh()
  }
  catch (err) {
    const failure = err as { statusCode?: number, data?: { detail?: unknown } }
    if (failure.statusCode === 401) {
      await navigateTo('/admin/login')
      return
    }
    actionError.value = typeof failure.data?.detail === 'string'
      ? failure.data.detail
      : 'Не удалось изменить статус заявки'
  }
  finally {
    busyId.value = null
  }
}

async function logout(): Promise<void> {
  await $fetch('/api/admin/logout', { method: 'POST' })
  await navigateTo('/admin/login')
}

function formatDate(isoDate: string): string {
  return isoDate.split('-').reverse().join('.')
}

function nights(checkIn: string, checkOut: string): number {
  return Math.round((Date.parse(checkOut) - Date.parse(checkIn)) / 86_400_000)
}

// Часовой пояс задан явно: иначе сервер (UTC) и браузер отрисуют разное время и гидратация разойдётся.
function formatCreated(isoDateTime: string): string {
  return new Date(isoDateTime).toLocaleString('ru-RU', {
    timeZone: 'Europe/Moscow',
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

useHead({
  title: 'Заявки — Kivana',
  meta: [{ name: 'robots', content: 'noindex' }],
})
</script>

<template>
  <section class="section">
    <div class="container">
      <div class="toolbar">
        <h1>Заявки</h1>
        <div class="toolbar__actions">
          <select v-model="statusFilter" aria-label="Статус заявки">
            <option value="">Все заявки</option>
            <option value="new">Новые</option>
            <option value="confirmed">Подтверждённые</option>
            <option value="cancelled">Отменённые</option>
          </select>
          <button class="button button--ghost" type="button" @click="logout">Выйти</button>
        </div>
      </div>

      <p v-if="actionError" class="notice notice--error">{{ actionError }}</p>

      <p v-if="error && error.statusCode !== 401" class="notice notice--error">
        Не удалось загрузить заявки. Обновите страницу через минуту.
      </p>

      <div v-else-if="data && data.items.length" class="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Создана</th>
              <th>Номер</th>
              <th>Гость</th>
              <th>Даты</th>
              <th>Гостей</th>
              <th>Комментарий</th>
              <th>Статус</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in data.items" :key="item.id">
              <td class="nowrap">{{ formatCreated(item.created_at) }}</td>
              <td>
                <NuxtLink :to="'/rooms/' + item.room.slug">{{ item.room.name }}</NuxtLink>
              </td>
              <td>
                <strong>{{ item.guest_name }}</strong><br>
                <a :href="'tel:' + item.phone.replace(/[^+\d]/g, '')">{{ item.phone }}</a><br>
                <a :href="'mailto:' + item.email">{{ item.email }}</a>
              </td>
              <td class="nowrap">
                {{ formatDate(item.check_in) }} — {{ formatDate(item.check_out) }}<br>
                <span class="muted">ночей: {{ nights(item.check_in, item.check_out) }}</span>
              </td>
              <td>{{ item.guests }}</td>
              <td class="comment">{{ item.comment || '—' }}</td>
              <td>
                <span class="status" :class="'status--' + item.status">{{ statusLabels[item.status] }}</span>
              </td>
              <td class="actions">
                <button
                  v-if="item.status !== 'confirmed'"
                  class="button button--small"
                  type="button"
                  :disabled="busyId === item.id"
                  @click="setStatus(item.id, 'confirmed')"
                >
                  Подтвердить
                </button>
                <button
                  v-if="item.status !== 'cancelled'"
                  class="button button--ghost button--small"
                  type="button"
                  :disabled="busyId === item.id"
                  @click="setStatus(item.id, 'cancelled')"
                >
                  Отменить
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="data" class="card empty">
        <p>Заявок с таким статусом пока нет.</p>
      </div>

      <div v-if="total > PAGE_SIZE" class="pager">
        <button class="button button--ghost button--small" type="button" :disabled="page === 0" @click="page--">
          Назад
        </button>
        <span class="muted">
          {{ page * PAGE_SIZE + 1 }}–{{ Math.min((page + 1) * PAGE_SIZE, total) }} из {{ total }}
        </span>
        <button class="button button--ghost button--small" type="button" :disabled="!hasNextPage" @click="page++">
          Вперёд
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}

.toolbar h1 {
  margin: 0;
}

.toolbar__actions {
  display: flex;
  gap: var(--space-2);
}

.toolbar select {
  padding: 11px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font: inherit;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}

th,
td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
}

th {
  color: var(--muted);
  font-weight: 600;
  white-space: nowrap;
}

tbody tr:last-child td {
  border-bottom: 0;
}

.nowrap {
  white-space: nowrap;
}

.comment {
  min-width: 180px;
  max-width: 280px;
}

.muted {
  color: var(--muted);
}

.status {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.85rem;
  white-space: nowrap;
}

.status--new {
  background: var(--surface-warm);
  color: var(--accent-dark);
}

.status--confirmed {
  background: #e7f3ec;
  color: var(--success);
}

.status--cancelled {
  background: #f1eeec;
  color: var(--muted);
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.button--small {
  padding: 6px 14px;
  font-size: 0.88rem;
  white-space: nowrap;
}

.empty {
  padding: var(--space-4);
  text-align: center;
  color: var(--muted);
}

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
</style>
