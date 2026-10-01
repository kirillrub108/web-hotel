<script setup lang="ts">
import type { AdminPromo, PromoForm, Room } from '~/types'

// Создание и изменение акции. Без promo — новая; client — выдача персональной акции этому клиенту.
// Персональность при изменении не меняется: user_id приходит из самой акции.
const props = defineProps<{
  rooms: Room[]
  promo?: AdminPromo
  client?: { id: number, full_name: string }
}>()
const emit = defineEmits<{ close: [], done: [], unauthorized: [] }>()

const DEFAULT_VALIDITY_DAYS = 30

function plusDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

const today = hotelToday()
const { promo } = props

const form = reactive<PromoForm>(
  promo
    ? promoToForm(promo)
    : {
        code: '',
        title: '',
        description: '',
        kind: 'percent',
        value: 10,
        valid_from: today,
        valid_to: plusDays(today, DEFAULT_VALIDITY_DAYS),
        min_nights: 1,
        room_id: null,
        user_id: props.client?.id ?? null,
        is_active: true,
      },
)

const dialog = ref<HTMLDialogElement | null>(null)
const errors = ref<Record<string, string>>({})
const serverError = ref('')
const isSending = ref(false)

const title = computed(() => {
  if (promo) {
    return 'Изменить акцию'
  }
  return props.client ? 'Выдать персональную акцию' : 'Новая акция'
})

onMounted(() => dialog.value?.showModal())

async function submit(): Promise<void> {
  errors.value = {}
  serverError.value = ''
  isSending.value = true
  try {
    await $fetch(promo ? `/api/admin/promos/${promo.id}` : '/api/admin/promos', {
      method: promo ? 'PATCH' : 'POST',
      body: { ...form, code: form.code.trim(), title: form.title.trim(), description: form.description.trim() },
    })
    emit('done')
  }
  catch (error) {
    if ((error as { statusCode?: number }).statusCode === 401) {
      emit('unauthorized')
      return
    }
    errors.value = apiFieldErrors(error)
    serverError.value = apiErrorMessage(error, 'Не удалось сохранить акцию. Проверьте поля и попробуйте ещё раз.')
  }
  finally {
    isSending.value = false
  }
}
</script>

<template>
  <dialog ref="dialog" class="dialog" @close="emit('close')">
    <form novalidate @submit.prevent="submit">
      <h2>{{ title }}</h2>
      <p v-if="client || promo?.user" class="dialog__subject">
        Клиент: {{ client?.full_name ?? promo?.user?.full_name }}. Код сможет применить только он.
      </p>

      <div class="field">
        <label for="promo-code">Промокод</label>
        <input id="promo-code" v-model="form.code" type="text" maxlength="32" autocomplete="off" placeholder="WELCOME10">
        <span v-if="errors.code" class="field__error">{{ errors.code }}</span>
        <span v-else class="dialog__hint">Латинские буквы, цифры, «-» и «_», от 3 до 32 символов. Регистр не важен.</span>
      </div>

      <div class="field">
        <label for="promo-title">Название</label>
        <input id="promo-title" v-model="form.title" type="text" maxlength="120" placeholder="Скидка 10% на любой номер">
        <span v-if="errors.title" class="field__error">{{ errors.title }}</span>
      </div>

      <div class="field">
        <label for="promo-description">Описание</label>
        <textarea id="promo-description" v-model="form.description" rows="2" maxlength="1000" />
        <span class="dialog__hint">Необязательно. Клиент увидит описание рядом с предложением.</span>
      </div>

      <div class="promo-row">
        <div class="field">
          <label for="promo-kind">Тип скидки</label>
          <select id="promo-kind" v-model="form.kind">
            <option value="percent">Процент</option>
            <option value="fixed">Фиксированная сумма</option>
          </select>
        </div>
        <div class="field">
          <label for="promo-value">{{ form.kind === 'percent' ? 'Процент' : 'Сумма, ₽' }}</label>
          <input id="promo-value" v-model.number="form.value" type="number" min="1" :max="form.kind === 'percent' ? 100 : undefined">
          <span v-if="errors.value" class="field__error">{{ errors.value }}</span>
        </div>
      </div>
      <p class="dialog__hint">
        Процентная скидка не больше 50% от стоимости проживания, фиксированная — не больше самой стоимости.
      </p>

      <div class="promo-row">
        <div class="field">
          <label for="promo-from">Действует с</label>
          <input id="promo-from" v-model="form.valid_from" type="date">
        </div>
        <div class="field">
          <label for="promo-to">Действует по</label>
          <input id="promo-to" v-model="form.valid_to" type="date" :min="form.valid_from">
        </div>
      </div>

      <div class="promo-row">
        <div class="field">
          <label for="promo-nights">Минимум ночей</label>
          <input id="promo-nights" v-model.number="form.min_nights" type="number" min="1">
          <span v-if="errors.min_nights" class="field__error">{{ errors.min_nights }}</span>
        </div>
        <div class="field">
          <label for="promo-room">Номер</label>
          <select id="promo-room" v-model="form.room_id">
            <option :value="null">Любой номер</option>
            <option v-for="room in rooms" :key="room.id" :value="room.id">{{ room.name }}</option>
          </select>
        </div>
      </div>

      <label class="checkbox">
        <input v-model="form.is_active" type="checkbox">
        <span>Акция активна</span>
      </label>

      <p v-if="serverError" class="notice notice--error">{{ serverError }}</p>

      <div class="dialog__actions">
        <button class="button button--ghost" type="button" :disabled="isSending" @click="dialog?.close()">
          Назад
        </button>
        <button class="button" type="submit" :disabled="isSending">
          {{ isSending ? 'Сохраняем…' : 'Сохранить' }}
        </button>
      </div>
    </form>
  </dialog>
</template>

<style scoped>
.promo-row {
  display: grid;
  gap: var(--space-2);
  grid-template-columns: 1fr 1fr;
}

@media (max-width: 560px) {
  .promo-row {
    grid-template-columns: 1fr;
  }
}
</style>
