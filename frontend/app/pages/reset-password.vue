<script setup lang="ts">
const route = useRoute()
const { clear } = useCurrentUser()
const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
const password = ref('')
const passwordError = ref('')
const errorText = ref('')
const isSending = ref(false)
const isDone = ref(false)

// Пароль меняется по кнопке, а не при открытии ссылки: почтовые сканеры заранее открывают ссылки из писем.
async function submit(): Promise<void> {
  passwordError.value = ''
  errorText.value = ''
  isSending.value = true
  try {
    await $fetch('/api/auth/reset-password', { method: 'POST', body: { token: token.value, password: password.value } })
    // Сброс завершает все сессии пользователя, в том числе в этом браузере.
    clear()
    isDone.value = true
  }
  catch (error) {
    passwordError.value = apiFieldErrors(error).password ?? ''
    if (!passwordError.value) {
      errorText.value = apiErrorMessage(error, 'Не удалось сменить пароль. Попробуйте ещё раз.')
    }
  }
  finally {
    isSending.value = false
  }
}

useHead({ title: 'Новый пароль — Kivana', meta: [{ name: 'robots', content: 'noindex' }] })
</script>

<template>
  <section class="section">
    <div class="container">
      <div v-if="isDone" class="card form-card">
        <h1>Пароль изменён</h1>
        <p class="notice notice--success">Готово. На всех устройствах выполнен выход — войдите с новым паролем.</p>
        <NuxtLink to="/login" class="button">Войти</NuxtLink>
      </div>

      <div v-else-if="!token" class="card form-card">
        <h1>Новый пароль</h1>
        <p class="notice notice--error">В ссылке нет кода. Откройте ссылку из письма целиком.</p>
        <NuxtLink to="/forgot-password" class="form-card__back">Запросить новое письмо</NuxtLink>
      </div>

      <form v-else class="card form-card" @submit.prevent="submit">
        <h1>Новый пароль</h1>

        <PasswordField
          id="password"
          v-model="password"
          label="Новый пароль"
          autocomplete="new-password"
          :error="passwordError"
        />

        <p v-if="errorText" class="notice notice--error">
          {{ errorText }}
          <NuxtLink to="/forgot-password" class="form-card__back">Запросить новое письмо</NuxtLink>
        </p>

        <button class="button" type="submit" :disabled="isSending">
          {{ isSending ? 'Сохраняем…' : 'Сохранить пароль' }}
        </button>
      </form>
    </div>
  </section>
</template>
