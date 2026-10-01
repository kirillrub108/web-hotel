<script setup lang="ts">
import type { AdminHousekeepingTask, HousekeepingBoard, HousekeepingSlot, HousekeepingStatus } from '~/types'

const { clear } = useCurrentUser()

async function toLogin(): Promise<void> {
  clear()
  await navigateTo({ path: '/login', query: { next: '/admin/housekeeping' } })
}

const today = hotelToday()
const date = ref(today)
// Пустое поле даты не отправляем: backend подставит сегодняшний день.
const query = computed(() => (date.value ? { date: date.value } : {}))

const { data: board, error } = await useFetch<HousekeepingBoard>('/api/admin/housekeeping', { query })

if (error.value?.statusCode === 401) {
  await toLogin()
}

const DAILY_SLOTS: Exclude<HousekeepingSlot, 'dnd'>[] = ['morning', 'day', 'evening']

const busyId = ref<number | null>(null)
const actionError = ref('')

async function mark(task: AdminHousekeepingTask, status: HousekeepingStatus): Promise<void> {
  actionError.value = ''
  busyId.value = task.id
  try {
    board.value = await $fetch<HousekeepingBoard>(`/api/admin/housekeeping/${task.id}`, {
      method: 'PATCH',
      body: { status },
    })
  }
  catch (err) {
    if ((err as { statusCode?: number }).statusCode === 401) {
      await toLogin()
      return
    }
    actionError.value = apiErrorMessage(err, 'Не удалось отметить уборку')
  }
  finally {
    busyId.value = null
  }
}

useHead({
  title: 'Уборка — Kivana',
  meta: [{ name: 'robots', content: 'noindex' }],
})
</script>

<template>
  <section class="section">
    <div class="container">
      <AdminNav />
      <div class="toolbar">
        <h1>Уборка</h1>
        <div class="toolbar__date">
          <label for="board-date">Дата</label>
          <input id="board-date" v-model="date" type="date">
          <button v-if="date !== today" class="button button--ghost button--small" type="button" @click="date = today">
            Сегодня
          </button>
        </div>
      </div>

      <p v-if="actionError" class="notice notice--error">{{ actionError }}</p>
      <p v-if="error && error.statusCode !== 401" class="notice notice--error">
        Не удалось загрузить расписание. Обновите страницу через минуту.
      </p>

      <template v-else-if="board">
        <h2>Уборки после выезда</h2>
        <p class="muted lead">Сначала номера, в которые сегодня заезжают новые гости.</p>
        <ul v-if="board.checkout.length" class="card list">
          <HousekeepingTaskRow
            v-for="task in board.checkout"
            :key="task.id"
            :task="task"
            :busy="busyId === task.id"
            @mark="mark(task, $event)"
          />
        </ul>
        <p v-else class="muted">Выездов нет.</p>

        <h2>Ежедневные уборки</h2>
        <div v-for="slot in DAILY_SLOTS" :key="slot" class="slot">
          <h3>{{ SLOT_LABELS[slot] }}</h3>
          <ul v-if="board.daily[slot].length" class="card list">
            <HousekeepingTaskRow
              v-for="task in board.daily[slot]"
              :key="task.id"
              :task="task"
              :busy="busyId === task.id"
              @mark="mark(task, $event)"
            />
          </ul>
          <p v-else class="muted">Нет уборок.</p>
        </div>

        <h2>Не беспокоить</h2>
        <p class="muted lead">Эти номера не убираем: гость отказался от уборки на этот день.</p>
        <ul v-if="board.dnd.length" class="card list">
          <HousekeepingTaskRow
            v-for="task in board.dnd"
            :key="task.id"
            :task="task"
            :busy="busyId === task.id"
            @mark="mark(task, $event)"
          />
        </ul>
        <p v-else class="muted">Таких номеров нет.</p>

        <h2>Заказы услуг уборки</h2>
        <div v-if="board.orders.length" class="card table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Время</th>
                <th>Услуга</th>
                <th>Номер и гость</th>
                <th>Комментарий</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="order in board.orders" :key="order.id">
                <td class="nowrap">{{ formatDateTime(order.scheduled_at) }}</td>
                <td>{{ order.service.title }}<template v-if="order.service.unit === 'per_item'"> × {{ order.quantity }}</template></td>
                <td>{{ order.booking.room.name }}, {{ order.booking.guest_name }}</td>
                <td>{{ order.comment ?? '—' }}</td>
                <td><StateBadge :status="order.status" :label="ORDER_STATUS_LABELS[order.status]" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="muted">Заказов нет.</p>
        <p class="muted lead">Статус заказа меняется в разделе «Заказы услуг».</p>
      </template>
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
  margin-bottom: var(--space-2);
}

.toolbar h1 {
  margin: 0;
}

.toolbar__date {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.toolbar__date input {
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font: inherit;
}

h2 {
  margin-top: var(--space-4);
  font-size: 1.4rem;
}

.lead {
  margin: 0 0 var(--space-1);
  font-size: 0.92rem;
}

.list {
  margin: 0 0 var(--space-2);
  padding: 0;
  list-style: none;
}

.slot h3 {
  margin: var(--space-2) 0 var(--space-1);
  font-size: 1rem;
  color: var(--muted);
}
</style>
