<script setup lang="ts">
import type { CurrentUser } from '~/types'

const { user, clear } = useCurrentUser()

const profile = reactive({ full_name: user.value?.full_name ?? '', phone: user.value?.phone ?? '' })
const profileErrors = ref<Record<string, string>>({})
const profileStatus = ref<'idle' | 'sending' | 'saved'>('idle')
const profileError = ref('')

async function saveProfile(): Promise<void> {
  profileErrors.value = {}
  profileError.value = ''
  profileStatus.value = 'sending'
  try {
    user.value = await $fetch<CurrentUser>('/api/account/profile', { method: 'PATCH', body: profile })
    profileStatus.value = 'saved'
  }
  catch (error) {
    profileErrors.value = apiFieldErrors(error)
    if (Object.keys(profileErrors.value).length === 0) {
      profileError.value = apiErrorMessage(error, 'Не удалось сохранить профиль. Попробуйте ещё раз.')
    }
    profileStatus.value = 'idle'
  }
}

const passwords = reactive({ current_password: '', new_password: '' })
const passwordErrors = ref<Record<string, string>>({})
const passwordStatus = ref<'idle' | 'sending' | 'saved'>('idle')
const passwordError = ref('')

async function changePassword(): Promise<void> {
  passwordErrors.value = {}
  passwordError.value = ''
  passwordStatus.value = 'sending'
  try {
    await $fetch('/api/auth/change-password', { method: 'POST', body: passwords })
    passwords.current_password = ''
    passwords.new_password = ''
    passwordStatus.value = 'saved'
  }
  catch (error) {
    passwordErrors.value = apiFieldErrors(error)
    if (Object.keys(passwordErrors.value).length === 0) {
      passwordError.value = apiErrorMessage(error, 'Не удалось сменить пароль. Попробуйте ещё раз.')
    }
    passwordStatus.value = 'idle'
  }
}

async function logout(): Promise<void> {
  await $fetch('/api/auth/logout', { method: 'POST' })
  clear()
  await navigateTo('/')
}

useHead({ title: 'Профиль — Kivana', meta: [{ name: 'robots', content: 'noindex' }] })
</script>

<template>
  <section class="section">
    <div class="container">
      <AccountNav />

      <div class="profile">
        <form class="card form-card" @submit.prevent="saveProfile">
          <h2>Профиль</h2>

          <div class="field">
            <label for="full_name">Имя и фамилия</label>
            <input id="full_name" v-model="profile.full_name" type="text" autocomplete="name" required>
            <span v-if="profileErrors.full_name" class="field__error">{{ profileErrors.full_name }}</span>
          </div>

          <div class="field">
            <label for="phone">Телефон</label>
            <input id="phone" v-model="profile.phone" type="tel" autocomplete="tel" placeholder="+7 900 000-00-00">
            <span v-if="profileErrors.phone" class="field__error">{{ profileErrors.phone }}</span>
          </div>

          <p v-if="profileStatus === 'saved'" class="notice notice--success">Профиль сохранён.</p>
          <p v-if="profileError" class="notice notice--error">{{ profileError }}</p>

          <button class="button" type="submit" :disabled="profileStatus === 'sending'">
            {{ profileStatus === 'sending' ? 'Сохраняем…' : 'Сохранить' }}
          </button>
        </form>

        <form class="card form-card" @submit.prevent="changePassword">
          <h2>Смена пароля</h2>

          <PasswordField
            id="current_password"
            v-model="passwords.current_password"
            label="Текущий пароль"
            autocomplete="current-password"
            :error="passwordErrors.current_password"
          />
          <PasswordField
            id="new_password"
            v-model="passwords.new_password"
            label="Новый пароль"
            autocomplete="new-password"
            :error="passwordErrors.new_password"
          />

          <p v-if="passwordStatus === 'saved'" class="notice notice--success">
            Пароль изменён. На других устройствах выполнен выход.
          </p>
          <p v-if="passwordError" class="notice notice--error">{{ passwordError }}</p>

          <button class="button" type="submit" :disabled="passwordStatus === 'sending'">
            {{ passwordStatus === 'sending' ? 'Сохраняем…' : 'Сменить пароль' }}
          </button>
        </form>
      </div>

      <button class="button button--ghost logout" type="button" @click="logout">Выйти из аккаунта</button>
    </div>
  </section>
</template>

<style scoped>
.profile {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--space-3);
  align-items: start;
}

.profile .form-card {
  max-width: none;
  margin: 0;
}

.logout {
  margin-top: var(--space-3);
}
</style>
