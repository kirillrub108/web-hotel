<script setup lang="ts">
const route = useRoute()
const { user, refresh } = useCurrentUser()
const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
const status = ref<'idle' | 'sending' | 'done'>('idle')
const errorText = ref('')

// Подтверждение — по кнопке, а не при открытии страницы: почтовые сканеры заранее открывают ссылки из писем.
async function confirm(): Promise<void> {
  errorText.value = ''
  status.value = 'sending'
  try {
    await $fetch('/api/auth/verify-email', { method: 'POST', body: { token: token.value } })
    await refresh()
    status.value = 'done'
  }
  catch (error) {
    errorText.value = apiErrorMessage(error, 'Не удалось подтвердить email. Попробуйте ещё раз.')
    status.value = 'idle'
  }
}

useHead({ title: 'Подтверждение email — Kivana', meta: [{ name: 'robots', content: 'noindex' }] })
</script>

<template>
  <section class="section">
    <div class="container">
      <div class="card form-card">
        <h1>Подтверждение email</h1>

        <template v-if="status === 'done'">
          <p class="notice notice--success">Email подтверждён. Спасибо!</p>
          <NuxtLink :to="user ? '/account' : '/login'" class="button">
            {{ user ? 'В личный кабинет' : 'Войти' }}
          </NuxtLink>
        </template>

        <p v-else-if="!token" class="notice notice--error">
          В ссылке нет кода подтверждения. Откройте ссылку из письма целиком.
        </p>

        <template v-else>
          <p>Нажмите кнопку, чтобы подтвердить адрес электронной почты.</p>
          <p v-if="errorText" class="notice notice--error">{{ errorText }}</p>
          <p v-if="errorText && user && !user.email_verified_at">
            Новое письмо можно отправить из <NuxtLink to="/account">личного кабинета</NuxtLink>.
          </p>
          <button class="button" type="button" :disabled="status === 'sending'" @click="confirm">
            {{ status === 'sending' ? 'Подтверждаем…' : 'Подтвердить email' }}
          </button>
        </template>
      </div>
    </div>
  </section>
</template>
