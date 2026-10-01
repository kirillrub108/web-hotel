<script setup lang="ts">
import type { AdminService, ServiceForm } from '~/types'

// Создание и изменение услуги. Без service — новая.
const props = defineProps<{ service?: AdminService }>()
const emit = defineEmits<{ close: [], done: [], unauthorized: [] }>()

const { service } = props

const form = reactive<ServiceForm>(
  service
    ? serviceToForm(service)
    : { slug: '', title: '', description: '', category: 'food', price: 0, unit: 'per_item', is_active: true, sort_order: 100 },
)

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
    await $fetch(service ? `/api/admin/services/${service.id}` : '/api/admin/services', {
      method: service ? 'PATCH' : 'POST',
      body: { ...form, slug: form.slug.trim(), title: form.title.trim(), description: form.description.trim() },
    })
    emit('done')
  }
  catch (error) {
    if ((error as { statusCode?: number }).statusCode === 401) {
      emit('unauthorized')
      return
    }
    errors.value = apiFieldErrors(error)
    serverError.value = apiErrorMessage(error, 'Не удалось сохранить услугу. Проверьте поля и попробуйте ещё раз.')
  }
  finally {
    isSending.value = false
  }
}
</script>

<template>
  <dialog ref="dialog" class="dialog" @close="emit('close')">
    <form novalidate @submit.prevent="submit">
      <h2>{{ service ? 'Изменить услугу' : 'Новая услуга' }}</h2>

      <div class="field">
        <label for="service-title">Название</label>
        <input id="service-title" v-model="form.title" type="text" maxlength="120" placeholder="Завтрак в номер">
        <span v-if="errors.title" class="field__error">{{ errors.title }}</span>
      </div>

      <div class="field">
        <label for="service-slug">Код</label>
        <input id="service-slug" v-model="form.slug" type="text" maxlength="60" autocomplete="off" placeholder="zavtrak-v-nomer">
        <span v-if="errors.slug" class="field__error">{{ errors.slug }}</span>
        <span v-else class="dialog__hint">Латинские буквы в нижнем регистре, цифры и «-». Должен быть уникальным.</span>
      </div>

      <div class="field">
        <label for="service-description">Описание</label>
        <textarea id="service-description" v-model="form.description" rows="3" maxlength="1000" />
      </div>

      <div class="service-row">
        <div class="field">
          <label for="service-category">Категория</label>
          <select id="service-category" v-model="form.category">
            <option v-for="(label, category) in CATEGORY_LABELS" :key="category" :value="category">{{ label }}</option>
          </select>
        </div>
        <div class="field">
          <label for="service-unit">Цена</label>
          <select id="service-unit" v-model="form.unit">
            <option v-for="(label, unit) in UNIT_LABELS" :key="unit" :value="unit">{{ label }}</option>
          </select>
        </div>
      </div>

      <div class="service-row">
        <div class="field">
          <label for="service-price">Стоимость, ₽</label>
          <input id="service-price" v-model.number="form.price" type="number" min="0">
          <span v-if="errors.price" class="field__error">{{ errors.price }}</span>
        </div>
        <div class="field">
          <label for="service-sort">Порядок показа</label>
          <input id="service-sort" v-model.number="form.sort_order" type="number" min="0">
          <span class="dialog__hint">Чем меньше число, тем выше в каталоге.</span>
        </div>
      </div>

      <label class="checkbox">
        <input v-model="form.is_active" type="checkbox">
        <span>Услуга показывается в каталоге и доступна для заказа</span>
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
.service-row {
  display: grid;
  gap: var(--space-2);
  grid-template-columns: 1fr 1fr;
}

@media (max-width: 560px) {
  .service-row {
    grid-template-columns: 1fr;
  }
}
</style>
