<script setup lang="ts">
const email = ref('')
const isSent = ref(false)
const isSending = ref(false)
const errorText = ref('')

async function submit(): Promise<void> {
  errorText.value = ''
  isSending.value = true
  try {
    await $fetch('/api/auth/forgot-password', { method: 'POST', body: { email: email.value } })
    isSent.value = true
  }
  catch (error) {
    errorText.value = apiErrorMessage(error, 'Не удалось отправить запрос. Проверьте адрес и попробуйте ещё раз.')
  }
  finally {
    isSending.value = false
  }
}

useHead({ title: 'Восстановление пароля — Kivana' })
</script>

<template>
  <section class="section">
    <div class="container">
      <div v-if="isSent" class="card form-card">
        <h1>Проверьте почту</h1>
        <p>
          Если аккаунт с адресом <strong>{{ email }}</strong> существует, мы отправили на него ссылку для сброса пароля.
          Ссылка действует 1 час.
        </p>
        <NuxtLink to="/login">Вернуться ко входу</NuxtLink>
      </div>

      <form v-else class="card form-card" @submit.prevent="submit">
        <h1>Восстановление пароля</h1>
        <p>Укажите email, с которым вы регистрировались, — пришлём ссылку для сброса пароля.</p>

        <div class="field">
          <label for="email">Электронная почта</label>
          <input id="email" v-model="email" type="email" autocomplete="email" required>
        </div>

        <p v-if="errorText" class="notice notice--error">{{ errorText }}</p>

        <button class="button" type="submit" :disabled="isSending">
          {{ isSending ? 'Отправляем…' : 'Отправить ссылку' }}
        </button>
      </form>
    </div>
  </section>
</template>
