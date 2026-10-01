<script setup lang="ts">
import type { AdminAction, AdminBooking } from '~/types'

const props = defineProps<{ booking: AdminBooking, action: AdminAction }>()
const emit = defineEmits<{ close: [], done: [], unauthorized: [] }>()

const TEXTS: Record<AdminAction, { title: string, button: string, label: string, hint: string }> = {
  confirm: {
    title: 'Подтвердить бронь',
    button: 'Подтвердить',
    label: 'Комментарий',
    hint: 'Необязательно. Гость увидит комментарий в истории брони.',
  },
  decline: {
    title: 'Отклонить заявку',
    button: 'Отклонить',
    label: 'Причина',
    hint: 'Обязательно. Причину гость получит в письме.',
  },
  cancel: {
    title: 'Отменить бронь',
    button: 'Отменить бронь',
    label: 'Причина',
    hint: 'Обязательно. Причину гость получит в письме.',
  },
}

const dialog = ref<HTMLDialogElement | null>(null)
const reason = ref('')
const errorText = ref('')
const isSending = ref(false)
const texts = computed(() => TEXTS[props.action])

// Нативный <dialog>: showModal() блокирует страницу под окном, Esc закрывает его без отдельного кода.
onMounted(() => dialog.value?.showModal())

async function submit(): Promise<void> {
  errorText.value = ''
  const text = reason.value.trim()
  if (props.action !== 'confirm' && text.length < 3) {
    errorText.value = 'Укажите причину — её увидит гость'
    return
  }

  isSending.value = true
  try {
    await $fetch(`/api/admin/bookings/${props.booking.id}/${props.action}`, {
      method: 'POST',
      body: { reason: text || null },
    })
    emit('done')
  }
  catch (error) {
    if ((error as { statusCode?: number }).statusCode === 401) {
      emit('unauthorized')
      return
    }
    errorText.value = apiErrorMessage(error, 'Не удалось выполнить действие. Попробуйте ещё раз.')
  }
  finally {
    isSending.value = false
  }
}
</script>

<template>
  <dialog ref="dialog" class="dialog" @close="emit('close')">
    <form novalidate @submit.prevent="submit">
      <h2>{{ texts.title }}</h2>
      <p class="dialog__subject">
        №{{ booking.id }}, {{ booking.room.name }}, {{ formatDate(booking.check_in) }} — {{ formatDate(booking.check_out) }},
        {{ booking.guest_name }}
      </p>

      <div class="field">
        <label for="admin-reason">{{ texts.label }}</label>
        <textarea id="admin-reason" v-model="reason" rows="3" maxlength="1000" />
        <span class="dialog__hint">{{ texts.hint }}</span>
      </div>

      <p v-if="errorText" class="notice notice--error">{{ errorText }}</p>

      <div class="dialog__actions">
        <button class="button button--ghost" type="button" :disabled="isSending" @click="dialog?.close()">
          Назад
        </button>
        <button class="button" type="submit" :disabled="isSending">
          {{ isSending ? 'Сохраняем…' : texts.button }}
        </button>
      </div>
    </form>
  </dialog>
</template>
