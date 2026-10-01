<script setup lang="ts">
const { user } = useCurrentUser()
const resendStatus = ref<'idle' | 'sending' | 'sent'>('idle')
const resendError = ref('')

async function resend(): Promise<void> {
  resendError.value = ''
  resendStatus.value = 'sending'
  try {
    await $fetch('/api/auth/resend-verification', { method: 'POST' })
    resendStatus.value = 'sent'
  }
  catch (error) {
    resendError.value = apiErrorMessage(error, 'Не удалось отправить письмо. Попробуйте позже.')
    resendStatus.value = 'idle'
  }
}

useHead({ title: 'Личный кабинет — Kivana', meta: [{ name: 'robots', content: 'noindex' }] })
</script>

<template>
  <section class="section">
    <div v-if="user" class="container">
      <AccountNav />
      <h1>Здравствуйте, {{ user.full_name }}!</h1>

      <div v-if="!user.email_verified_at" class="card banner">
        <p>
          <strong>Подтвердите email.</strong>
          Мы отправили ссылку на {{ user.email }}. Если письма нет, проверьте папку «Спам» или отправьте его ещё раз.
        </p>
        <p v-if="resendStatus === 'sent'" class="notice notice--success">Письмо отправлено.</p>
        <p v-if="resendError" class="notice notice--error">{{ resendError }}</p>
        <button
          class="button button--ghost"
          type="button"
          :disabled="resendStatus === 'sending'"
          @click="resend"
        >
          {{ resendStatus === 'sending' ? 'Отправляем…' : 'Отправить письмо ещё раз' }}
        </button>
      </div>

      <div class="card overview">
        <p><span class="overview__label">Email</span>{{ user.email }}</p>
        <p><span class="overview__label">Телефон</span>{{ user.phone || 'не указан' }}</p>
        <NuxtLink to="/account/profile">Изменить профиль или пароль</NuxtLink>
      </div>
    </div>
  </section>
</template>

<style scoped>
.banner,
.overview {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding: var(--space-3);
}

.banner {
  background: var(--surface-warm);
}

.banner p,
.overview p {
  margin: 0;
}

.overview__label {
  display: inline-block;
  min-width: 100px;
  color: var(--muted);
}
</style>
