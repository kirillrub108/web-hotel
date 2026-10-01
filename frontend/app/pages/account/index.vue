<script setup lang="ts">
import type { Booking, Promo } from '~/types'

const { user } = useCurrentUser()
const { data: bookings } = await useFetch<Booking[]>('/api/account/bookings')
const { data: offers } = await useFetch<Promo[]>('/api/account/promos', { default: () => [] })

// Ближайшая бронь — предстоящая или текущая с самой ранней датой заезда.
const nearest = computed(() =>
  (bookings.value ?? [])
    .filter(item => ['pending', 'confirmed', 'in_stay'].includes(item.display_status))
    .sort((a, b) => a.check_in.localeCompare(b.check_in))[0],
)
const resendStatus = ref<'idle' | 'sending' | 'sent'>('idle')
const resendError = ref('')

async function resend(): Promise<void> {
  resendError.value = ''
  resendStatus.value = 'sending'
  try {
    await $fetch('/api/auth/resend-verification', { method: 'POST' })
    resendStatus.value = 'sent'
  }
  catch (error) {
    resendError.value = apiErrorMessage(error, 'Не удалось отправить письмо. Попробуйте позже.')
    resendStatus.value = 'idle'
  }
}

useHead({ title: 'Личный кабинет — Kivana', meta: [{ name: 'robots', content: 'noindex' }] })
</script>

<template>
  <section class="section">
    <div v-if="user" class="container">
      <AccountNav />
      <h1>Здравствуйте, {{ user.full_name }}!</h1>

      <div v-if="!user.email_verified_at" class="card banner">
        <p>
          <strong>Подтвердите email.</strong>
          Мы отправили ссылку на {{ user.email }}. Если письма нет, проверьте папку «Спам» или отправьте его ещё раз.
        </p>
        <p v-if="resendStatus === 'sent'" class="notice notice--success">Письмо отправлено.</p>
        <p v-if="resendError" class="notice notice--error">{{ resendError }}</p>
        <button
          class="button button--ghost"
          type="button"
          :disabled="resendStatus === 'sending'"
          @click="resend"
        >
          {{ resendStatus === 'sending' ? 'Отправляем…' : 'Отправить письмо ещё раз' }}
        </button>
      </div>

      <div class="card overview">
        <h2>Ближайшая бронь</h2>
        <template v-if="nearest">
          <p>
            <StatusBadge :status="nearest.display_status" />
          </p>
          <p>
            <strong>{{ nearest.room.name }}</strong>,
            {{ formatDate(nearest.check_in) }} — {{ formatDate(nearest.check_out) }}, {{ nightsLabel(nearest.nights) }}
          </p>
          <NuxtLink :to="`/account/bookings/${nearest.id}`">Подробнее о брони</NuxtLink>
        </template>
        <template v-else>
          <p>Предстоящих броней нет.</p>
          <NuxtLink to="/rooms">Выбрать номер</NuxtLink>
        </template>
      </div>

      <div class="card overview">
        <h2>Персональные предложения</h2>
        <ul v-if="offers.length" class="offers">
          <li v-for="offer in offers" :key="offer.id" class="offer">
            <p class="offer__head">
              <strong>{{ offer.title }}</strong>
              <span class="tag">{{ promoValueLabel(offer) }}</span>
              <span class="tag">{{ offer.is_personal ? 'Только для вас' : 'Для всех гостей' }}</span>
            </p>
            <p v-if="offer.description" class="offer__text">{{ offer.description }}</p>
            <p class="offer__code">Промокод: <code>{{ offer.code }}</code></p>
            <ul class="offer__conditions">
              <li v-for="condition in promoConditions(offer)" :key="condition">{{ condition }}</li>
            </ul>
          </li>
        </ul>
        <p v-else class="muted">Сейчас предложений нет. Они появятся здесь, когда отель выдаст вам скидку.</p>
        <NuxtLink v-if="offers.length" to="/rooms">Выбрать номер</NuxtLink>
      </div>

      <div class="card overview">
        <p><span class="overview__label">Email</span>{{ user.email }}</p>
        <p><span class="overview__label">Телефон</span>{{ user.phone || 'не указан' }}</p>
        <NuxtLink to="/account/profile">Изменить профиль или пароль</NuxtLink>
      </div>
    </div>
  </section>
</template>

<style scoped>
.banner,
.overview {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding: var(--space-3);
}

.banner {
  background: var(--surface-warm);
}

@media (max-width: 1023.98px) {
  .overview a {
    display: inline-flex;
    align-items: center;
    min-height: var(--tap);
  }
}

.banner p,
.overview p,
.overview h2 {
  margin: 0;
}

.offers {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 100%;
  margin: 0;
  padding: 0;
  list-style: none;
}

.offer {
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--surface-warm);
}

.offer p {
  margin: 0 0 6px;
}

.offer .tag {
  background: var(--surface);
}

.offer__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
}

.offer__text {
  color: var(--muted);
}

.offer__code code {
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--surface);
  font-weight: 700;
}

.offer__conditions {
  margin: 0;
  padding-left: 18px;
  color: var(--muted);
  font-size: 0.9rem;
}

.muted {
  color: var(--muted);
}

.overview__label {
  display: inline-block;
  min-width: 100px;
  color: var(--muted);
}
</style>
