<script setup lang="ts">
const form = reactive({ full_name: '', email: '', password: '', consent: false })
const fieldErrors = ref<Record<string, string>>({})
const errorText = ref('')
const isSending = ref(false)
const sentTo = ref('')

async function submit(): Promise<void> {
  fieldErrors.value = {}
  errorText.value = ''
  isSending.value = true
  try {
    await $fetch('/api/auth/register', { method: 'POST', body: form })
    sentTo.value = form.email.trim()
  }
  catch (error) {
    fieldErrors.value = apiFieldErrors(error)
    if (Object.keys(fieldErrors.value).length === 0) {
      errorText.value = apiErrorMessage(error, 'Не удалось зарегистрироваться. Проверьте поля и попробуйте ещё раз.')
    }
  }
  finally {
    isSending.value = false
  }
}

useHead({ title: 'Регистрация — Kivana' })
</script>

<template>
  <section class="section">
    <div class="container">
      <div v-if="sentTo" class="card form-card">
        <h1>Проверьте почту</h1>
        <p>
          Мы отправили письмо на <strong>{{ sentTo }}</strong>. Перейдите по ссылке из него, чтобы подтвердить email.
          Войти можно уже сейчас.
        </p>
        <NuxtLink to="/login" class="button">Войти</NuxtLink>
      </div>

      <form v-else class="card form-card" @submit.prevent="submit">
        <h1>Регистрация</h1>

        <div class="field">
          <label for="full_name">Имя и фамилия</label>
          <input id="full_name" v-model="form.full_name" type="text" autocomplete="name" required>
          <span v-if="fieldErrors.full_name" class="field__error">{{ fieldErrors.full_name }}</span>
        </div>

        <div class="field">
          <label for="email">Электронная почта</label>
          <input id="email" v-model="form.email" type="email" autocomplete="email" required>
          <span v-if="fieldErrors.email" class="field__error">{{ fieldErrors.email }}</span>
        </div>

        <PasswordField
          id="password"
          v-model="form.password"
          label="Пароль"
          autocomplete="new-password"
          :error="fieldErrors.password"
        />

        <div class="field">
          <label class="checkbox">
            <input v-model="form.consent" type="checkbox" required>
            <span>
              Я согласен на обработку персональных данных согласно
              <NuxtLink to="/privacy" target="_blank">политике конфиденциальности</NuxtLink>
            </span>
          </label>
          <span v-if="fieldErrors.consent" class="field__error">{{ fieldErrors.consent }}</span>
        </div>

        <p v-if="errorText" class="notice notice--error">{{ errorText }}</p>

        <button class="button" type="submit" :disabled="isSending">
          {{ isSending ? 'Отправляем…' : 'Зарегистрироваться' }}
        </button>

        <div class="form-card__links">
          <NuxtLink to="/login">Уже есть аккаунт? Войти</NuxtLink>
        </div>
      </form>
    </div>
  </section>
</template>
