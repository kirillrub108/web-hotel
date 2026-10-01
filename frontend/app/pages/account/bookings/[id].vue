<script setup lang="ts">
import type { BookingDetail, GuestServiceOrder, Hotel, Service } from '~/types'

const route = useRoute()
const id = route.params.id as string

const { data: detail, error } = await useFetch<BookingDetail>(`/api/account/bookings/${id}`)
const { data: hotel } = await useFetch<Hotel>('/api/hotel', { key: 'hotel' })
const { data: services } = await useFetch<Service[]>('/api/services', { key: 'services', default: () => [] })

if (!detail.value) {
  throw error.value?.statusCode === 404
    ? createError({ statusCode: 404, message: 'Бронь не найдена', fatal: true })
    : createError({ statusCode: 503, message: 'Сайт временно недоступен', fatal: true })
}

const isConfirming = ref(false)
const isCancelling = ref(false)
const cancelError = ref('')

// Срок онлайн-отмены прошёл, а проживание ещё не началось: отменить можно только по телефону.
const deadlinePassed = computed(() =>
  detail.value?.booking.display_status === 'confirmed' && !detail.value.can_cancel,
)

async function cancel(): Promise<void> {
  cancelError.value = ''
  isCancelling.value = true
  try {
    detail.value = await $fetch<BookingDetail>(`/api/account/bookings/${id}/cancel`, { method: 'POST' })
    isConfirming.value = false
  }
  catch (err) {
    cancelError.value = apiErrorMessage(err, 'Не удалось отменить бронь. Попробуйте ещё раз или позвоните нам.')
  }
  finally {
    isCancelling.value = false
  }
}

const cancellingOrderId = ref<number | null>(null)
const orderError = ref('')

function onDetailChanged(updated: BookingDetail): void {
  detail.value = updated
}

async function cancelOrder(order: GuestServiceOrder): Promise<void> {
  orderError.value = ''
  cancellingOrderId.value = order.id
  try {
    detail.value = await $fetch<BookingDetail>(`/api/account/service-orders/${order.id}/cancel`, { method: 'POST' })
  }
  catch (err) {
    orderError.value = apiErrorMessage(err, 'Не удалось отменить заказ. Попробуйте ещё раз или позвоните нам.')
  }
  finally {
    cancellingOrderId.value = null
  }
}

useHead({ title: 'Бронь — Kivana', meta: [{ name: 'robots', content: 'noindex' }] })
</script>

<template>
  <section v-if="detail" class="section">
    <div class="container">
      <AccountNav />
      <p class="crumbs"><NuxtLink to="/account/bookings">Мои брони</NuxtLink> / Бронь №{{ detail.booking.id }}</p>

      <div class="layout">
        <div class="card block">
          <div class="block__head">
            <h1>{{ detail.booking.room.name }}</h1>
            <StatusBadge :status="detail.booking.display_status" />
          </div>

          <dl class="facts">
            <dt>Даты</dt>
            <dd>{{ formatDate(detail.booking.check_in) }} — {{ formatDate(detail.booking.check_out) }}, {{ nightsLabel(detail.booking.nights) }}</dd>
            <dt>Гостей</dt>
            <dd>{{ detail.booking.guests }}</dd>
            <dt>Гость</dt>
            <dd>{{ detail.booking.guest_name }}, {{ detail.booking.phone }}</dd>
            <dt>Стоимость</dt>
            <dd>
              {{ nightsLabel(detail.booking.nights) }} × {{ formatRubles(detail.booking.price_per_night) }}
              <template v-if="detail.booking.discount">
                , скидка {{ formatRubles(detail.booking.discount) }}
                <template v-if="detail.booking.promo">(промокод {{ detail.booking.promo.code }})</template>
              </template>
              = <strong>{{ formatRubles(detail.booking.total_price) }}</strong>
            </dd>
            <template v-if="detail.booking.comment">
              <dt>Комментарий</dt>
              <dd>{{ detail.booking.comment }}</dd>
            </template>
          </dl>

          <div v-if="detail.can_cancel" class="cancel">
            <p v-if="detail.booking.status === 'pending'" class="cancel__text">
              Заявку можно отменить в любой момент, пока её рассматривают.
            </p>
            <p v-else-if="detail.cancel_deadline" class="cancel__text">
              Бесплатно отменить бронь онлайн можно до {{ formatDateTime(detail.cancel_deadline) }} (время московское).
            </p>

            <button v-if="!isConfirming" class="button button--ghost" type="button" @click="isConfirming = true">
              Отменить бронь
            </button>
            <div v-else class="cancel__confirm">
              <p><strong>Отменить бронь?</strong> Вернуть её не получится — понадобится новая заявка.</p>
              <div class="cancel__actions">
                <button class="button" type="button" :disabled="isCancelling" @click="cancel">
                  {{ isCancelling ? 'Отменяем…' : 'Да, отменить' }}
                </button>
                <button class="button button--ghost" type="button" :disabled="isCancelling" @click="isConfirming = false">
                  Не отменять
                </button>
              </div>
            </div>
            <p v-if="cancelError" class="notice notice--error">{{ cancelError }}</p>
          </div>

          <p v-else-if="deadlinePassed && detail.cancel_deadline" class="notice cancel__closed">
            Срок онлайн-отмены истёк {{ formatDateTime(detail.cancel_deadline) }}.
            Чтобы отменить бронь, позвоните нам<template v-if="hotel">: <a :href="'tel:' + hotel.phone.replace(/[^+\d]/g, '')">{{ hotel.phone }}</a></template>.
          </p>
        </div>

        <div class="card block">
          <h2>История</h2>
          <BookingTimeline :events="detail.events" />
        </div>
      </div>

      <div v-if="detail.can_order || detail.orders.length" class="card block extra">
        <h2>Услуги и еда в номер</h2>

        <ul v-if="detail.orders.length" class="orders">
          <li v-for="order in detail.orders" :key="order.id" class="orders__item">
            <div>
              <strong>{{ order.service.title }}</strong>
              <span v-if="order.service.unit === 'per_item'"> × {{ order.quantity }}</span>
              <p class="muted orders__meta">
                {{ formatDateTime(order.scheduled_at) }}<template v-if="order.comment"> · {{ order.comment }}</template>
              </p>
            </div>
            <div class="orders__side">
              <span class="orders__sum">{{ formatRubles(order.total) }}</span>
              <StateBadge :status="order.status" :label="ORDER_STATUS_LABELS[order.status]" />
              <button
                v-if="order.can_cancel"
                class="button button--ghost button--small"
                type="button"
                :disabled="cancellingOrderId === order.id"
                @click="cancelOrder(order)"
              >
                {{ cancellingOrderId === order.id ? 'Отменяем…' : 'Отменить' }}
              </button>
            </div>
          </li>
        </ul>
        <p v-if="orderError" class="notice notice--error">{{ orderError }}</p>
        <p v-if="detail.orders.length" class="orders__total">
          Итого по услугам: <strong>{{ formatRubles(detail.services_total) }}</strong> — оплата на ресепшене.
          Отменить можно только новый заказ, принятый — по телефону<template v-if="hotel"> {{ hotel.phone }}</template>.
        </p>

        <template v-if="detail.can_order">
          <h3>Новый заказ</h3>
          <ServiceOrderForm :detail="detail" :services="services ?? []" @ordered="onDetailChanged" />
        </template>
      </div>
      <p v-else-if="detail.booking.status === 'pending'" class="muted">
        Заказать услуги и еду в номер можно после подтверждения брони.
      </p>

      <div v-if="detail.housekeeping.length" class="card block extra">
        <h2>Уборка</h2>
        <p class="muted">
          Выберите удобное время ежедневной уборки или «Не беспокоить». Изменить можно даты позже сегодняшней.
          Уборка после выезда выполняется без вас.
        </p>
        <HousekeepingPrefs :detail="detail" @updated="onDetailChanged" />
      </div>
    </div>
  </section>
</template>

<style scoped>
.crumbs {
  color: var(--muted);
  font-size: 0.9rem;
}

.layout {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: 1.3fr 1fr;
  align-items: start;
}

.block {
  padding: var(--space-3);
}

.block__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.block__head h1 {
  margin: 0;
}

.facts {
  display: grid;
  gap: 8px var(--space-2);
  grid-template-columns: max-content 1fr;
  margin: var(--space-3) 0;
}

.facts dt {
  color: var(--muted);
}

.facts dd {
  margin: 0;
}

.cancel {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border);
}

.cancel p {
  margin: 0;
}

.cancel__text {
  color: var(--muted);
}

.cancel__actions {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
  margin-top: var(--space-1);
}

.cancel__closed {
  background: var(--surface-warm);
}

.extra {
  margin-top: var(--space-3);
}

.orders {
  margin: 0 0 var(--space-2);
  padding: 0;
  list-style: none;
}

.orders__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.orders__item p {
  margin: 0;
  font-size: 0.9rem;
}

.orders__side {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.orders__sum {
  font-weight: 600;
}

.orders__total {
  font-size: 0.95rem;
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
