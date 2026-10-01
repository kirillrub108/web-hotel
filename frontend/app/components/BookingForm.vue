<script setup lang="ts">
import type { Booking, Promo, Quote, Room } from '~/types'

const props = defineProps<{ room: Room }>()

const { user } = useCurrentUser()
const today = hotelToday()

// Имя и телефон предзаполняются из профиля; в брони они сохраняются снимком и их можно поправить.
const form = reactive({
  guest_name: user.value?.full_name ?? '',
  phone: user.value?.phone ?? '',
  check_in: '',
  check_out: '',
  guests: 1,
  comment: '',
})

// Промокод: promoInput — то, что набрано, appliedCode — то, что учтено в котировке и уйдёт в заявке.
const promoInput = ref('')
const appliedCode = ref('')
const promoError = ref('')

// Предложения клиента: общие и персональные акции, не занятые бронями. Для гостя без входа список не запрашивается.
const { data: offers } = useFetch<Promo[]>('/api/account/promos', { default: () => [], immediate: Boolean(user.value) })
const roomOffers = computed(() => offers.value.filter(offer => offer.room_id === null || offer.room_id === props.room.id))

// Выбор из списка и ввод кода — одно и то же значение: выбранная акция подставляет свой код.
const selectedOffer = computed({
  get: () => roomOffers.value.find(offer => offer.code === appliedCode.value)?.code ?? '',
  set: (code: string) => {
    promoInput.value = code
    appliedCode.value = code
  },
})

function applyPromo(): void {
  appliedCode.value = promoInput.value.trim()
}

const errors = ref<Record<string, string>>({})
const serverError = ref('')
const isSending = ref(false)
const result = ref<Booking | null>(null)

const quote = ref<Quote | null>(null)
const quoteError = ref('')
let quoteRequest = 0

// Живая котировка: при каждом изменении дат или числа гостей backend считает цену и проверяет даты.
// Ответ устаревшего запроса отбрасывается по номеру, чтобы на экране не оказалась цена за прежние даты.
watch(
  () => [form.check_in, form.check_out, form.guests, appliedCode.value] as const,
  async ([checkIn, checkOut, guests, promoCode]) => {
    quote.value = null
    quoteError.value = ''
    promoError.value = ''
    if (!checkIn || !checkOut || checkOut <= checkIn || guests < 1) {
      return
    }
    const request = ++quoteRequest
    try {
      const fresh = await $fetch<Quote>(`/api/rooms/${props.room.slug}/quote`, {
        query: { check_in: checkIn, check_out: checkOut, guests, ...(promoCode ? { promo_code: promoCode } : {}) },
      })
      if (request === quoteRequest) {
        quote.value = fresh
      }
    }
    catch (error) {
      if (request === quoteRequest) {
        const message = apiErrorMessage(error, 'Не удалось рассчитать стоимость. Проверьте даты.')
        // Котировка отвечает 400 только на неподходящий промокод; ошибки дат приходят как 422.
        if (promoCode && (error as { statusCode?: number }).statusCode === 400) {
          promoError.value = message
        }
        else {
          quoteError.value = message
        }
      }
    }
  },
)

// Даты проверяет котировка: отправить заявку можно, только когда она подтвердила, что номер свободен.
const canSubmit = computed(() => quote.value?.available === true && !isSending.value)

function validate(): boolean {
  const found: Record<string, string> = {}
  if (form.guest_name.trim().length < 2) {
    found.guest_name = 'Укажите имя полностью'
  }
  const phoneDigits = form.phone.replace(/\D/g, '').length
  if (phoneDigits < 10 || phoneDigits > 15) {
    found.phone = 'Укажите телефон полностью, например +7 900 000-00-00'
  }
  errors.value = found
  return Object.keys(found).length === 0
}

async function submit(): Promise<void> {
  serverError.value = ''
  if (!validate()) {
    return
  }

  isSending.value = true
  try {
    result.value = await $fetch<Booking>('/api/bookings', {
      method: 'POST',
      body: {
        room_id: props.room.id,
        guest_name: form.guest_name.trim(),
        phone: form.phone.trim(),
        check_in: form.check_in,
        check_out: form.check_out,
        guests: form.guests,
        comment: form.comment.trim() || null,
        promo_code: appliedCode.value || null,
      },
    })
  }
  catch (error) {
    errors.value = apiFieldErrors(error)
    serverError.value = apiErrorMessage(error, 'Не удалось отправить заявку. Попробуйте ещё раз или позвоните нам.')
  }
  finally {
    isSending.value = false
  }
}
</script>

<template>
  <div class="card booking">
    <template v-if="result">
      <h2>Заявка отправлена</h2>
      <p><StatusBadge :status="result.display_status" /></p>

      <template v-if="result.status === 'confirmed'">
        <p>Бронь подтверждена: номер ждёт вас {{ formatDate(result.check_in) }}. Письмо с деталями отправили на {{ user?.email }}.</p>
      </template>
      <template v-else-if="result.status === 'pending'">
        <p>Администратор проверит заявку вручную и ответит письмом. Почему понадобилась проверка:</p>
        <ul class="booking__reasons">
          <li v-for="reason in result.reasons" :key="reason">{{ reason }}</li>
        </ul>
      </template>
      <template v-else>
        <p>Не получилось подтвердить бронь:</p>
        <ul class="booking__reasons">
          <li v-for="reason in result.reasons" :key="reason">{{ reason }}</li>
        </ul>
      </template>

      <NuxtLink class="button" :to="`/account/bookings/${result.id}`">Открыть бронь</NuxtLink>
    </template>

    <form v-else novalidate @submit.prevent="submit">
      <h2>Бронирование</h2>
      <p class="booking__lead">
        Онлайн-оплата не нужна. Бронь на свободные даты обычно подтверждается сразу, в остальных случаях её проверит администратор.
      </p>

      <div class="field">
        <label for="guest_name">Имя и фамилия</label>
        <input id="guest_name" v-model="form.guest_name" type="text" autocomplete="name" maxlength="120">
        <span v-if="errors.guest_name" class="field__error">{{ errors.guest_name }}</span>
      </div>

      <div class="field">
        <label for="phone">Телефон</label>
        <input id="phone" v-model="form.phone" type="tel" inputmode="tel" autocomplete="tel" maxlength="40" placeholder="+7 900 000-00-00">
        <span v-if="errors.phone" class="field__error">{{ errors.phone }}</span>
      </div>

      <div class="booking__row">
        <div class="field">
          <label for="check_in">Заезд</label>
          <input id="check_in" v-model="form.check_in" type="date" :min="today">
        </div>

        <div class="field">
          <label for="check_out">Выезд</label>
          <input id="check_out" v-model="form.check_out" type="date" :min="form.check_in || today">
        </div>
      </div>

      <div class="field">
        <label for="guests">Гостей</label>
        <input id="guests" v-model.number="form.guests" type="number" inputmode="numeric" min="1" :max="room.capacity">
      </div>

      <div class="field">
        <label for="comment">Комментарий</label>
        <textarea id="comment" v-model="form.comment" rows="3" maxlength="1000" placeholder="Ранний заезд, детская кроватка, парковка" />
        <span class="booking__hint">С комментарием заявку проверит администратор.</span>
      </div>

      <div v-if="user" class="field">
        <label for="promo_code">Промокод</label>
        <select v-if="roomOffers.length" id="promo_offer" v-model="selectedOffer" aria-label="Ваши предложения">
          <option value="">Выбрать из ваших предложений</option>
          <option v-for="offer in roomOffers" :key="offer.id" :value="offer.code">
            {{ offer.title }} ({{ promoValueLabel(offer) }})
          </option>
        </select>
        <div class="booking__promo">
          <input
            id="promo_code"
            v-model="promoInput"
            type="text"
            maxlength="32"
            autocomplete="off"
            placeholder="Или введите код"
            @keydown.enter.prevent="applyPromo"
          >
          <button class="button button--ghost" type="button" @click="applyPromo">Применить</button>
        </div>
        <span v-if="promoError" class="field__error" aria-live="polite">{{ promoError }}</span>
        <span v-else-if="quote?.promo_title" class="booking__hint">Применена акция «{{ quote.promo_title }}».</span>
      </div>

      <div v-if="quote" class="booking__quote" aria-live="polite">
        <template v-if="quote.available">
          <p>{{ nightsLabel(quote.nights) }} × {{ formatRubles(quote.price_per_night) }} = {{ formatRubles(quote.subtotal) }}</p>
          <p v-if="quote.discount">Скидка: −{{ formatRubles(quote.discount) }}</p>
          <p class="booking__total">Итого: {{ formatRubles(quote.total) }}</p>
        </template>
        <p v-else class="notice notice--error">{{ quote.unavailable_reason }}</p>
      </div>
      <p v-else-if="quoteError" class="notice notice--error" aria-live="polite">{{ quoteError }}</p>
      <p v-else class="booking__hint">Выберите даты — покажем стоимость и проверим, свободен ли номер.</p>

      <p v-if="serverError" class="notice notice--error">{{ serverError }}</p>

      <button class="button booking__submit" type="submit" :disabled="!canSubmit">
        {{ isSending ? 'Отправляем…' : 'Забронировать' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.booking {
  padding: var(--space-2);
}

@media (min-width: 640px) {
  .booking {
    padding: var(--space-3);
  }
}

.booking__lead,
.booking__hint {
  color: var(--muted);
  font-size: 0.92rem;
}

.booking form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.booking__promo {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

@media (min-width: 640px) {
  .booking__promo {
    flex-direction: row;
  }
}

.booking__promo input {
  flex: 1;
  min-width: 0;
}

.booking__row {
  display: grid;
  gap: var(--space-2);
}

@media (min-width: 640px) {
  .booking__row {
    grid-template-columns: 1fr 1fr;
  }
}

.booking__quote {
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--surface-warm);
}

.booking__quote p {
  margin: 0;
}

.booking__quote .booking__total {
  margin-top: 6px;
  font-size: 1.1rem;
  font-weight: 700;
}

.booking__reasons {
  padding-left: 20px;
}

.booking__submit {
  margin-top: var(--space-1);
}
</style>
