<script setup lang="ts">
import type { Room } from '~/types'

const props = defineProps<{ room: Room }>()

const today = new Date().toISOString().slice(0, 10)

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

function validate(): boolean {
  const found: Record<string, string> = {}

  if (form.guest_name.trim().length < 2) {
    found.guest_name = 'Укажите имя полностью'
  }
  if (form.phone.trim().length < 5) {
    found.phone = 'Укажите телефон для связи'
  }
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email)) {
    found.email = 'Проверьте адрес электронной почты'
  }
  if (!form.check_in) {
    found.check_in = 'Выберите дату заезда'
  }
  if (!form.check_out) {
    found.check_out = 'Выберите дату выезда'
  }
  if (form.check_in && form.check_out && form.check_out <= form.check_in) {
    found.check_out = 'Дата выезда должна быть позже даты заезда'
  }
  if (form.guests < 1 || form.guests > props.room.capacity) {
    found.guests = 'Максимальное число гостей в номере — ' + props.room.capacity
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
    const detail = (error as { data?: { detail?: unknown } }).data?.detail
    serverError.value = typeof detail === 'string'
      ? detail
      : 'Не удалось отправить заявку. Попробуйте ещё раз или позвоните нам.'
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
        <input id="guest_name" v-model="form.guest_name" type="text" autocomplete="name">
        <span v-if="errors.guest_name" class="field__error">{{ errors.guest_name }}</span>
      </div>

      <div class="booking__row">
        <div class="field">
          <label for="phone">Телефон</label>
          <input id="phone" v-model="form.phone" type="tel" autocomplete="tel" placeholder="+7 900 000-00-00">
          <span v-if="errors.phone" class="field__error">{{ errors.phone }}</span>
        </div>

        <div class="field">
          <label for="email">Электронная почта</label>
          <input id="email" v-model="form.email" type="email" autocomplete="email">
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
        <textarea id="comment" v-model="form.comment" rows="3" placeholder="Ранний заезд, детская кроватка, парковка" />
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
