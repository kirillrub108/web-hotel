<script setup lang="ts">
const form = reactive({ username: '', password: '' })
const errorText = ref('')
const isSending = ref(false)

async function submit(): Promise<void> {
  errorText.value = ''
  isSending.value = true
  try {
    await $fetch('/api/admin/login', { method: 'POST', body: form })
    await navigateTo('/admin')
  }
  catch (error) {
    const detail = (error as { data?: { detail?: unknown } }).data?.detail
    errorText.value = typeof detail === 'string' ? detail : 'Не удалось войти. Попробуйте ещё раз.'
  }
  finally {
    isSending.value = false
  }
}

useHead({
  title: 'Вход для администратора — Kivana',
  meta: [{ name: 'robots', content: 'noindex' }],
})
</script>

<template>
  <section class="section">
    <div class="container">
      <form class="card login" @submit.prevent="submit">
        <h1>Вход для администратора</h1>

        <div class="field">
          <label for="username">Логин</label>
          <input id="username" v-model="form.username" type="text" autocomplete="username" required>
        </div>

        <div class="field">
          <label for="password">Пароль</label>
          <input id="password" v-model="form.password" type="password" autocomplete="current-password" required>
        </div>

        <p v-if="errorText" class="notice notice--error">{{ errorText }}</p>

        <button class="button" type="submit" :disabled="isSending">
          {{ isSending ? 'Входим…' : 'Войти' }}
        </button>
      </form>
    </div>
  </section>
</template>

<style scoped>
.login {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-width: 420px;
  margin: 0 auto;
  padding: var(--space-4) var(--space-3);
}

.login h1 {
  font-size: 1.6rem;
}
</style>
