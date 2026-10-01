<script setup lang="ts">
import type { AdminAction, AdminBooking, AdminBookingDetail, AdminBookingPage, BookingEvent, BookingStatus } from '~/types'

const PAGE_SIZE = 20

// «На разборе» — первая вкладка и открывается по умолчанию: эти заявки ждут решения.
const TABS: { value: BookingStatus | '', label: string }[] = [
  { value: 'pending', label: 'На разборе' },
  { value: 'confirmed', label: 'Подтверждённые' },
  { value: 'declined', label: 'Отклонённые' },
  { value: 'cancelled', label: 'Отменённые' },
  { value: '', label: 'Все' },
]

const { clear } = useCurrentUser()

// Сессия могла истечь, пока страница открыта: тогда API отвечает 401 и нужен повторный вход.
async function toLogin(): Promise<void> {
  clear()
  await navigateTo({ path: '/login', query: { next: '/admin' } })
}

// Ссылки из карточки клиента открывают нужную вкладку: /admin?status=confirmed.
const route = useRoute()
const requested = TABS.find(tab => tab.value !== '' && tab.value === route.query.status)
const statusFilter = ref<BookingStatus | ''>(requested?.value ?? 'pending')
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
  await toLogin()
}

const total = computed(() => data.value?.total ?? 0)
const hasNextPage = computed(() => (page.value + 1) * PAGE_SIZE < total.value)

const active = ref<{ booking: AdminBooking, action: AdminAction } | null>(null)

async function onActionDone(): Promise<void> {
  active.value = null
  history.value = {}
  await refresh()
}

// Заезд ещё не прошёл: подтверждённую бронь можно отменить до даты выезда.
function canCancelConfirmed(item: AdminBooking): boolean {
  return item.status === 'confirmed' && item.display_status !== 'completed'
}

// История заявки загружается по кнопке, чтобы список не тянул журнал всех броней.
const history = ref<Record<number, BookingEvent[]>>({})
const historyError = ref('')

async function toggleHistory(id: number): Promise<void> {
  historyError.value = ''
  if (history.value[id]) {
    const rest = { ...history.value }
    delete rest[id]
    history.value = rest
    return
  }
  try {
    const detail = await $fetch<AdminBookingDetail>(`/api/admin/bookings/${id}`)
    history.value = { ...history.value, [id]: detail.events }
  }
  catch (err) {
    historyError.value = apiErrorMessage(err, 'Не удалось загрузить историю заявки')
  }
}

async function logout(): Promise<void> {
  await $fetch('/api/auth/logout', { method: 'POST' })
  clear()
  await navigateTo('/login')
}

useHead({
  title: 'Заявки — Kivana',
  meta: [{ name: 'robots', content: 'noindex' }],
})
</script>

<template>
  <section class="section">
    <div class="container">
      <AdminNav />
      <div class="toolbar">
        <h1>Заявки</h1>
        <button class="button button--ghost" type="button" @click="logout">Выйти</button>
      </div>

      <div class="tabs" role="tablist" aria-label="Статус заявок">
        <button
          v-for="tab in TABS"
          :key="tab.value"
          class="tabs__item"
          :class="{ 'tabs__item--active': statusFilter === tab.value }"
          type="button"
          role="tab"
          :aria-selected="statusFilter === tab.value"
          @click="statusFilter = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>

      <p v-if="historyError" class="notice notice--error">{{ historyError }}</p>

      <p v-if="error && error.statusCode !== 401" class="notice notice--error">
        Не удалось загрузить заявки. Обновите страницу через минуту.
      </p>

      <div v-else-if="data && data.items.length" class="card table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Создана</th>
              <th>Номер</th>
              <th>Гость</th>
              <th>Даты</th>
              <th>Сумма</th>
              <th>Статус и причины</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <template v-for="item in data.items" :key="item.id">
              <tr>
                <td data-label="Создана" class="nowrap">№{{ item.id }}<br><span class="muted">{{ formatDateTime(item.created_at) }}</span></td>
                <td data-label="Номер">
                  <NuxtLink :to="'/rooms/' + item.room.slug">{{ item.room.name }}</NuxtLink>
                </td>
                <td data-label="Гость">
                  <strong>{{ item.guest_name }}</strong>
                  <span v-if="item.user.crm_status !== 'regular'" class="tag crm">{{ CRM_LABELS[item.user.crm_status] }}</span><br>
                  <a :href="'tel:' + item.phone.replace(/[^+\d]/g, '')">{{ item.phone }}</a><br>
                  <a :href="'mailto:' + item.user.email">{{ item.user.email }}</a>
                </td>
                <td data-label="Даты" class="nowrap">
                  {{ formatDate(item.check_in) }} — {{ formatDate(item.check_out) }}<br>
                  <span class="muted">{{ nightsLabel(item.nights) }}, гостей: {{ item.guests }}</span>
                </td>
                <td data-label="Сумма" class="nowrap">
                  {{ formatRubles(item.total_price) }}
                  <template v-if="item.promo">
                    <br><span class="muted">−{{ formatRubles(item.discount) }}, {{ item.promo.code }}</span>
                  </template>
                </td>
                <td data-label="Статус" class="reasons">
                  <StatusBadge :status="item.display_status" />
                  <ul v-if="item.reasons.length">
                    <li v-for="reason in item.reasons" :key="reason">{{ reason }}</li>
                  </ul>
                  <p v-if="item.reason_codes.length" class="codes">{{ item.reason_codes.join(', ') }}</p>
                  <p v-if="item.comment" class="comment">«{{ item.comment }}»</p>
                </td>
                <td class="actions">
                  <template v-if="item.status === 'pending'">
                    <button class="button button--small" type="button" @click="active = { booking: item, action: 'confirm' }">
                      Подтвердить
                    </button>
                    <button class="button button--ghost button--small" type="button" @click="active = { booking: item, action: 'decline' }">
                      Отклонить
                    </button>
                  </template>
                  <button
                    v-if="item.status === 'pending' || canCancelConfirmed(item)"
                    class="button button--ghost button--small"
                    type="button"
                    @click="active = { booking: item, action: 'cancel' }"
                  >
                    Отменить
                  </button>
                  <button class="link-button" type="button" @click="toggleHistory(item.id)">
                    {{ history[item.id] ? 'Скрыть историю' : 'История' }}
                  </button>
                </td>
              </tr>
              <tr v-if="history[item.id]" class="history">
                <td colspan="7">
                  <BookingTimeline :events="history[item.id] ?? []" />
                </td>
              </tr>
            </template>
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

    <AdminActionDialog
      v-if="active"
      :booking="active.booking"
      :action="active.action"
      @close="active = null"
      @done="onActionDone"
      @unauthorized="toLogin"
    />
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

.crm {
  margin-left: 6px;
}

.reasons {
  min-width: 0;
}

@media (min-width: 640px) {
  .reasons {
    min-width: 180px;
    max-width: 320px;
  }
}

@media (min-width: 1280px) {
  .reasons {
    min-width: 220px;
  }
}

.reasons ul {
  margin: 8px 0 0;
  padding-left: 18px;
}

.codes,
.comment {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 0.85rem;
}

.codes {
  font-family: ui-monospace, monospace;
}

.history td {
  background: var(--bg);
}
</style>
