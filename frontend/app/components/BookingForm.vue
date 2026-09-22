<script setup lang="ts">
import type { Room } from '~/types'

const props = defineProps<{ room: Room }>()

const today = new Date().toISOString().slice(0, 10)
const MAX_CHECK_IN_ADVANCE_DAYS = 365
const MAX_STAY_NIGHTS = 90

const form = reactive({
  guest_name: '',
  phone: '',
  email: '',
  check_in: '',
  check_out: '',
  guests: 1,
  comment: '',
})

const errors = ref<Record<string, string>>({})
const serverError = ref('')
const isSent = ref(false)
const isSending = ref(false)

function daysBetween(from: string, to: string): number {
  return Math.round((new Date(to).getTime() - new Date(from).getTime()) / 86400000)
}

function validate(): boolean {
  const found: Record<string, string> = {}

  if (form.guest_name.trim().length < 2) {
    found.guest_name = 'Укажите имя полностью'
  }
  const phoneDigits = form.phone.replace(/\D/g, '').length
  if (phoneDigits < 10 || phoneDigits > 15) {
    found.phone = 'Укажите телефон полностью, например +7 900 000-00-00'
  }
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email)) {
    found.email = 'Проверьте адрес электронной почты'
  }
  if (!form.check_in) {
    found.check_in = 'Выберите дату заезда'
  }
  else if (form.check_in < today) {
    found.check_in = 'Дата заезда не может быть в прошлом'
  }
  else if (daysBetween(today, form.check_in) > MAX_CHECK_IN_ADVANCE_DAYS) {
    found.check_in = 'Дата заезда не может быть позже, чем через год'
  }
  if (!form.check_out) {
    found.check_out = 'Выберите дату выезда'
  }
  if (form.check_in && form.check_out && form.check_out <= form.check_in) {
    found.check_out = 'Дата выезда должна быть позже даты заезда'
  }
  else if (form.check_in && form.check_out && daysBetween(form.check_in, form.check_out) > MAX_STAY_NIGHTS) {
    found.check_out = `Максимальная длительность проживания — ${MAX_STAY_NIGHTS} ночей`
  }
  if (form.guests < 1 || form.guests > props.room.capacity) {
    found.guests = 'Максимальное число гостей в номере — ' + props.room.capacity
  }

  errors.value = found
  return Object.keys(found).length === 0
}

function errorMessage(error: unknown): string {
  const detail = (error as { data?: { detail?: unknown } }).data?.detail
  if (typeof detail === 'string') {
    return detail
  }
  // 422 от FastAPI приходит списком ошибок. Русский текст есть только у наших валидаторов,
  // и Pydantic добавляет к нему префикс «Value error, »; остальные сообщения — английские.
  const first = Array.isArray(detail) ? (detail[0] as { msg?: unknown }) : undefined
  if (typeof first?.msg === 'string' && first.msg.startsWith('Value error, ')) {
    return first.msg.replace('Value error, ', '')
  }
  return 'Не удалось отправить заявку. Попробуйте ещё раз или позвоните нам.'
}

async function submit(): Promise<void> {
  serverError.value = ''
  if (!validate()) {
    return
  }

  isSending.value = true
  try {
    await $fetch('/api/bookings', {
      method: 'POST',
      body: {
        room_id: props.room.id,
        guest_name: form.guest_name.trim(),
        phone: form.phone.trim(),
        email: form.email.trim(),
        check_in: form.check_in,
        check_out: form.check_out,
        guests: form.guests,
        comment: form.comment.trim() || null,
      },
    })
    isSent.value = true
  }
  catch (error) {
    serverError.value = errorMessage(error)
  }
  finally {
    isSending.value = false
  }
}
</script>

<template>
  <div class="card booking">
    <h2>Заявка на бронирование</h2>

    <p v-if="isSent" class="notice notice--success">
      Заявка принята. Мы перезвоним в течение рабочего дня и подтвердим бронь.
    </p>

    <form v-else novalidate @submit.prevent="submit">
      <p class="booking__lead">
        Оплата не требуется: это предварительная заявка, администратор свяжется с вами.
      </p>

      <div class="field">
        <label for="guest_name">Имя и фамилия</label>
        <input id="guest_name" v-model="form.guest_name" type="text" autocomplete="name" maxlength="120">
        <span v-if="errors.guest_name" class="field__error">{{ errors.guest_name }}</span>
      </div>

      <div class="booking__row">
        <div class="field">
          <label for="phone">Телефон</label>
          <input id="phone" v-model="form.phone" type="tel" autocomplete="tel" maxlength="40" placeholder="+7 900 000-00-00">
          <span v-if="errors.phone" class="field__error">{{ errors.phone }}</span>
        </div>

        <div class="field">
          <label for="email">Электронная почта</label>
          <input id="email" v-model="form.email" type="email" autocomplete="email" maxlength="120">
          <span v-if="errors.email" class="field__error">{{ errors.email }}</span>
        </div>
      </div>

      <div class="booking__row">
        <div class="field">
          <label for="check_in">Заезд</label>
          <input id="check_in" v-model="form.check_in" type="date" :min="today">
          <span v-if="errors.check_in" class="field__error">{{ errors.check_in }}</span>
        </div>

        <div class="field">
          <label for="check_out">Выезд</label>
          <input id="check_out" v-model="form.check_out" type="date" :min="form.check_in || today">
          <span v-if="errors.check_out" class="field__error">{{ errors.check_out }}</span>
        </div>
      </div>

      <div class="field">
        <label for="guests">Гостей</label>
        <input id="guests" v-model.number="form.guests" type="number" min="1" :max="room.capacity">
        <span v-if="errors.guests" class="field__error">{{ errors.guests }}</span>
      </div>

      <div class="field">
        <label for="comment">Комментарий</label>
        <textarea id="comment" v-model="form.comment" rows="3" maxlength="1000" placeholder="Ранний заезд, детская кроватка, парковка" />
      </div>

      <p v-if="serverError" class="notice notice--error">{{ serverError }}</p>

      <button class="button booking__submit" type="submit" :disabled="isSending">
        {{ isSending ? 'Отправляем…' : 'Отправить заявку' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.booking {
  padding: var(--space-3);
}

.booking__lead {
  color: var(--muted);
  font-size: 0.95rem;
}

.booking form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.booking__row {
  display: grid;
  gap: var(--space-2);
  grid-template-columns: 1fr 1fr;
}

.booking__submit {
  margin-top: var(--space-1);
}

@media (max-width: 560px) {
  .booking__row {
    grid-template-columns: 1fr;
  }
}
</style>
