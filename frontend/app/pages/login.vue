<script setup lang="ts">
import type { CurrentUser } from '~/types'

const route = useRoute()
const { user } = useCurrentUser()
const form = reactive({ email: '', password: '' })
const errorText = ref('')
const isSending = ref(false)

// Возвращаем только на страницы этого сайта: адреса вида «//example.com» отбрасываются.
function nextPath(loggedIn: CurrentUser): string {
  const next = route.query.next
  if (typeof next === 'string' && next.startsWith('/') && !next.startsWith('//')) {
    return next
  }
  return loggedIn.role === 'admin' ? '/admin' : '/account'
}

async function submit(): Promise<void> {
  errorText.value = ''
  isSending.value = true
  try {
    user.value = await $fetch<CurrentUser>('/api/auth/login', { method: 'POST', body: form })
    await navigateTo(nextPath(user.value))
  }
  catch (error) {
    errorText.value = apiErrorMessage(error, 'Не удалось войти. Попробуйте ещё раз.')
  }
  finally {
    isSending.value = false
  }
}

useHead({ title: 'Вход — Kivana' })
</script>

<template>
  <section class="section">
    <div class="container">
      <form class="card form-card" @submit.prevent="submit">
        <h1>Вход</h1>

        <div class="field">
          <label for="email">Электронная почта</label>
          <input id="email" v-model="form.email" type="email" inputmode="email" autocomplete="username" required>
        </div>

        <PasswordField id="password" v-model="form.password" label="Пароль" autocomplete="current-password" />

        <p v-if="errorText" class="notice notice--error">{{ errorText }}</p>

        <button class="button" type="submit" :disabled="isSending">
          {{ isSending ? 'Входим…' : 'Войти' }}
        </button>

        <div class="form-card__links">
          <NuxtLink to="/forgot-password">Забыли пароль?</NuxtLink>
          <NuxtLink to="/register">Зарегистрироваться</NuxtLink>
        </div>
      </form>
    </div>
  </section>
</template>
