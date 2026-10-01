<script setup lang="ts">
import type { AdminServiceOrder, OrderStatus } from '~/types'

const { clear } = useCurrentUser()

async function toLogin(): Promise<void> {
  clear()
  await navigateTo({ path: '/login', query: { next: '/admin/service-orders' } })
}

// По умолчанию — очередь новых заказов; пустое значение — все статусы.
const status = ref<OrderStatus | ''>('new')
const date = ref('')
const query = computed(() => ({
  ...(status.value ? { status: status.value } : {}),
  ...(date.value ? { date: date.value } : {}),
}))

const { data, error, refresh } = await useFetch<AdminServiceOrder[]>('/api/admin/service-orders', {
  query,
  default: () => [],
})

if (error.value?.statusCode === 401) {
  await toLogin()
}

// Действия по статусу заказа: кнопка и статус, в который она переводит. Совпадает с ORDER_TRANSITIONS backend.
const ACTIONS: Record<OrderStatus, { label: string, to: OrderStatus }[]> = {
  new: [{ label: 'Принять', to: 'accepted' }, { label: 'Отменить', to: 'cancelled' }],
  accepted: [{ label: 'Выполнен', to: 'done' }, { label: 'Отменить', to: 'cancelled' }],
  done: [],
  cancelled: [],
}

const busyId = ref<number | null>(null)
const actionError = ref('')

async function changeStatus(order: AdminServiceOrder, to: OrderStatus): Promise<void> {
  actionError.value = ''
  busyId.value = order.id
  try {
    await $fetch(`/api/admin/service-orders/${order.id}`, { method: 'PATCH', body: { status: to } })
    await refresh()
  }
  catch (err) {
    if ((err as { statusCode?: number }).statusCode === 401) {
      await toLogin()
      return
    }
    actionError.value = apiErrorMessage(err, 'Не удалось изменить заказ')
  }
  finally {
    busyId.value = null
  }
}

useHead({
  title: 'Заказы услуг — Kivana',
  meta: [{ name: 'robots', content: 'noindex' }],
})
</script>

<template>
  <section class="section">
    <div class="container">
      <AdminNav />
      <h1>Заказы услуг</h1>

      <div class="filters">
        <div class="field">
          <label for="orders-status">Статус</label>
          <select id="orders-status" v-model="status">
            <option value="">Все</option>
            <option v-for="(label, value) in ORDER_STATUS_LABELS" :key="value" :value="value">{{ label }}</option>
          </select>
        </div>
        <div class="field">
          <label for="orders-date">Дата заказа</label>
          <input id="orders-date" v-model="date" type="date">
        </div>
        <button v-if="date" class="button button--ghost button--small" type="button" @click="date = ''">
          Сбросить дату
        </button>
      </div>

      <p v-if="actionError" class="notice notice--error">{{ actionError }}</p>
      <p v-if="error && error.statusCode !== 401" class="notice notice--error">
        Не удалось загрузить заказы. Обновите страницу через минуту.
      </p>

      <div v-else-if="data && data.length" class="card table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Время</th>
              <th>Услуга</th>
              <th>Сумма</th>
              <th>Номер и гость</th>
              <th>Комментарий</th>
              <th>Статус</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="order in data" :key="order.id">
              <td data-label="Время" class="nowrap">{{ formatDateTime(order.scheduled_at) }}</td>
              <td data-label="Услуга">
                {{ order.service.title }}<template v-if="order.service.unit === 'per_item'"> × {{ order.quantity }}</template>
                <br>
                <span v-if="!order.service.is_active" class="muted">Услуга отключена</span>
                <span v-else class="muted">{{ CATEGORY_LABELS[order.service.category] }}</span>
              </td>
              <td data-label="Сумма" class="nowrap">{{ formatRubles(order.total) }}</td>
              <td data-label="Номер и гость">
                {{ order.booking.room.name }}, бронь №{{ order.booking.id }}<br>
                <span class="muted">{{ order.booking.guest_name }}, {{ order.booking.phone }}</span>
              </td>
              <td data-label="Комментарий">{{ order.comment ?? '—' }}</td>
              <td data-label="Статус"><StateBadge :status="order.status" :label="ORDER_STATUS_LABELS[order.status]" /></td>
              <td class="actions">
                <button
                  v-for="action in ACTIONS[order.status]"
                  :key="action.to"
                  class="link-button"
                  type="button"
                  :disabled="busyId === order.id"
                  @click="changeStatus(order, action.to)"
                >
                  {{ action.label }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="card empty">
        <p>Заказов по выбранным условиям нет.</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.filters {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
}

.filters .field {
  flex: 1 1 100%;
}

@media (min-width: 640px) {
  .filters .field {
    flex: 0 1 auto;
  }
}
</style>
