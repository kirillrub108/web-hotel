<script setup lang="ts">
import type { BookingDetail, Service } from '~/types'

// Заказ услуги или еды в номер. Время должно попасть в окно проживания, а еду принимают только в часы кухни:
// браузер подсказывает границы, окончательно проверяет backend.
const props = defineProps<{ detail: BookingDetail, services: Service[] }>()
const emit = defineEmits<{ ordered: [detail: BookingDetail] }>()

const MAX_QUANTITY = 20

const form = reactive({ service_id: null as number | null, quantity: 1, scheduled_at: '', comment: '' })
const error = ref('')
const isSending = ref(false)

const groups = computed(() => groupServices(props.services))
const selected = computed(() => props.services.find(service => service.id === form.service_id))
// Услуга «за проживание» заказывается один раз за заказ: количество не спрашиваем.
const hasQuantity = computed(() => selected.value?.unit === 'per_item')
const total = computed(() => (selected.value ? selected.value.price * (hasQuantity.value ? form.quantity : 1) : 0))
const minTime = computed(() => (props.detail.order_window ? toLocalInput(props.detail.order_window.start) : undefined))
const maxTime = computed(() => (props.detail.order_window ? toLocalInput(props.detail.order_window.end) : undefined))

async function submit(): Promise<void> {
  error.value = ''
  if (!selected.value) {
    error.value = 'Выберите услугу'
    return
  }
  if (!form.scheduled_at) {
    error.value = 'Укажите дату и время'
    return
  }
  isSending.value = true
  try {
    const detail = await $fetch<BookingDetail>(`/api/account/bookings/${props.detail.booking.id}/service-orders`, {
      method: 'POST',
      body: {
        service_id: selected.value.id,
        quantity: hasQuantity.value ? form.quantity : 1,
        scheduled_at: form.scheduled_at,
        comment: form.comment,
      },
    })
    form.service_id = null
    form.quantity = 1
    form.scheduled_at = ''
    form.comment = ''
    emit('ordered', detail)
  }
  catch (err) {
    error.value = apiErrorMessage(err, 'Не удалось оформить заказ. Проверьте поля и попробуйте ещё раз.')
  }
  finally {
    isSending.value = false
  }
}
</script>

<template>
  <form class="order" novalidate @submit.prevent="submit">
    <div class="field">
      <label for="order-service">Услуга</label>
      <select id="order-service" v-model="form.service_id">
        <option :value="null" disabled>Выберите услугу</option>
        <optgroup v-for="group in groups" :key="group.category" :label="group.title">
          <option v-for="service in group.services" :key="service.id" :value="service.id">
            {{ service.title }} — {{ servicePriceLabel(service) }}
          </option>
        </optgroup>
      </select>
      <span v-if="selected" class="muted hint">{{ selected.description }}</span>
    </div>

    <div class="order__row">
      <div v-if="hasQuantity" class="field">
        <label for="order-quantity">Количество</label>
        <input id="order-quantity" v-model.number="form.quantity" type="number" inputmode="numeric" min="1" :max="MAX_QUANTITY">
      </div>
      <div class="field">
        <label for="order-time">Дата и время</label>
        <input id="order-time" v-model="form.scheduled_at" type="datetime-local" :min="minTime" :max="maxTime">
        <span v-if="selected?.category === 'food'" class="muted hint">
          Еду принимаем с {{ detail.room_service_hours.replace('–', ' до ') }}.
        </span>
        <span v-else class="muted hint">Время московское, в пределах вашего проживания.</span>
      </div>
    </div>

    <div class="field">
      <label for="order-comment">Комментарий</label>
      <textarea id="order-comment" v-model="form.comment" rows="2" maxlength="500" placeholder="Например, без лука" />
    </div>

    <p v-if="selected" class="order__total">
      Сумма: <strong>{{ formatRubles(total) }}</strong>, оплата на ресепшене.
    </p>
    <p v-if="error" class="notice notice--error">{{ error }}</p>

    <button class="button" type="submit" :disabled="isSending">
      {{ isSending ? 'Оформляем…' : 'Заказать' }}
    </button>
  </form>
</template>

<style scoped>
.order {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
  max-width: 560px;
}

.order .field,
.order__row {
  width: 100%;
}

.order__row {
  display: grid;
  gap: var(--space-2);
  grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr));
}

.hint {
  font-size: 0.85rem;
}

.order__total,
.order .notice {
  margin: 0;
}
</style>
