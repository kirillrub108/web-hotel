<script setup lang="ts">
import type { BookingDetail, Hotel } from '~/types'

const route = useRoute()
const id = route.params.id as string

const { data: detail, error } = await useFetch<BookingDetail>(`/api/account/bookings/${id}`)
const { data: hotel } = await useFetch<Hotel>('/api/hotel', { key: 'hotel' })

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
              <template v-if="detail.booking.discount">, скидка {{ formatRubles(detail.booking.discount) }}</template>
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

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
