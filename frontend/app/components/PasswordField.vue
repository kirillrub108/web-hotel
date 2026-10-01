<script setup lang="ts">
const props = defineProps<{
  id: string
  label: string
  autocomplete: 'new-password' | 'current-password'
  error?: string
}>()

const password = defineModel<string>({ required: true })
const isVisible = ref(false)
const minLength = useRuntimeConfig().public.passwordMinLength
const isNewPassword = computed(() => props.autocomplete === 'new-password')

// Длина в символах Unicode, как её считает сервер: строка разбивается по кодовым точкам после NFC.
const missing = computed(() => Math.max(minLength - [...password.value.normalize('NFC')].length, 0))

function symbols(count: number): string {
  const lastTwo = count % 100
  const last = count % 10
  if (lastTwo >= 11 && lastTwo <= 14) {
    return 'символов'
  }
  if (last === 1) {
    return 'символ'
  }
  return last >= 2 && last <= 4 ? 'символа' : 'символов'
}
</script>

<template>
  <div class="field">
    <label :for="id">{{ label }}</label>
    <div class="password">
      <input
        :id="id"
        v-model="password"
        :type="isVisible ? 'text' : 'password'"
        :autocomplete="autocomplete"
        :aria-invalid="Boolean(error)"
        :aria-describedby="isNewPassword ? `${id}-hint` : undefined"
        required
      >
      <button
        class="password__toggle"
        type="button"
        :aria-pressed="isVisible"
        :aria-label="isVisible ? 'Скрыть пароль' : 'Показать пароль'"
        @click="isVisible = !isVisible"
      >
        {{ isVisible ? 'Скрыть' : 'Показать' }}
      </button>
    </div>
    <p v-if="isNewPassword" :id="`${id}-hint`" class="password__hint">
      <span :class="{ 'password__hint--ok': missing === 0 }">
        {{ missing > 0 ? `Ещё ${missing} ${symbols(missing)} до минимума в ${minLength}.` : 'Длина подходит.' }}
      </span>
      Используйте фразу из 3–4 слов: её легко запомнить и трудно подобрать.
    </p>
    <span v-if="error" class="field__error">{{ error }}</span>
  </div>
</template>

<style scoped>
.password {
  display: flex;
  gap: var(--space-1);
}

.password input {
  flex: 1;
  min-width: 0;
}

.password__toggle {
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--muted);
  font: inherit;
  font-size: 0.85rem;
  cursor: pointer;
}

.password__toggle:hover {
  color: var(--accent-dark);
}

.password__hint {
  margin: 0;
  color: var(--muted);
  font-size: 0.85rem;
}

.password__hint--ok {
  color: var(--success);
}
</style>
