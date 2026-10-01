<script setup lang="ts">
import type { Room, RoomForm } from '~/types'

// Изменение номера: цена, описание и доступность для новых броней.
const props = defineProps<{ room: Room }>()
const emit = defineEmits<{ close: [], done: [], unauthorized: [] }>()

const { room } = props

const form = reactive<RoomForm>({
  price_per_night: room.price_per_night,
  description: room.description,
  is_available: room.is_available,
})

const dialog = ref<HTMLDialogElement | null>(null)
const errors = ref<Record<string, string>>({})
const serverError = ref('')
const isSending = ref(false)

onMounted(() => dialog.value?.showModal())

async function submit(): Promise<void> {
  errors.value = {}
  serverError.value = ''
  isSending.value = true
  try {
    await $fetch(`/api/admin/rooms/${room.id}`, {
      method: 'PATCH',
      body: { ...form, description: form.description.trim() },
    })
    emit('done')
  }
  catch (error) {
    if ((error as { statusCode?: number }).statusCode === 401) {
      emit('unauthorized')
      return
    }
    errors.value = apiFieldErrors(error)
    serverError.value = apiErrorMessage(error, 'Не удалось сохранить номер. Проверьте поля и попробуйте ещё раз.')
  }
  finally {
    isSending.value = false
  }
}
</script>

<template>
  <dialog ref="dialog" class="dialog" @close="emit('close')">
    <form novalidate @submit.prevent="submit">
      <h2>Номер «{{ room.name }}»</h2>

      <div class="field">
        <label for="room-price">Цена за ночь, ₽</label>
        <input id="room-price" v-model.number="form.price_per_night" type="number" inputmode="numeric" min="1">
        <span v-if="errors.price_per_night" class="field__error">{{ errors.price_per_night }}</span>
      </div>

      <div class="field">
        <label for="room-description">Описание</label>
        <textarea id="room-description" v-model="form.description" rows="6" maxlength="2000" />
        <span v-if="errors.description" class="field__error">{{ errors.description }}</span>
      </div>

      <label class="checkbox">
        <input v-model="form.is_available" type="checkbox">
        <span>Номер можно бронировать</span>
      </label>
      <span class="dialog__hint">
        Если снять галочку, новые брони станут недоступны, а уже оформленные останутся без изменений.
      </span>

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
