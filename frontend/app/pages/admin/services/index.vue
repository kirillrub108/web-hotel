<script setup lang="ts">
import type { AdminService } from '~/types'

const { clear } = useCurrentUser()

async function toLogin(): Promise<void> {
  clear()
  await navigateTo({ path: '/login', query: { next: '/admin/services' } })
}

const { data, error, refresh } = await useFetch<AdminService[]>('/api/admin/services')

if (error.value?.statusCode === 401) {
  await toLogin()
}

const editing = ref<AdminService | 'new' | null>(null)
const actionError = ref('')

async function runAction(action: () => Promise<void>, fallback: string): Promise<void> {
  actionError.value = ''
  try {
    await action()
    await refresh()
  }
  catch (err) {
    if ((err as { statusCode?: number }).statusCode === 401) {
      await toLogin()
      return
    }
    actionError.value = apiErrorMessage(err, fallback)
  }
}

function toggle(service: AdminService): Promise<void> {
  return runAction(() => setServiceActive(service, !service.is_active), 'Не удалось изменить услугу')
}

function remove(service: AdminService): Promise<void> {
  if (!confirm(`Удалить услугу «${service.title}»? Это действие нельзя отменить.`)) {
    return Promise.resolve()
  }
  return runAction(
    async () => {
      await $fetch(`/api/admin/services/${service.id}`, { method: 'DELETE' })
    },
    'Не удалось удалить услугу',
  )
}

async function onSaved(): Promise<void> {
  editing.value = null
  await refresh()
}

useHead({
  title: 'Услуги — Kivana',
  meta: [{ name: 'robots', content: 'noindex' }],
})
</script>

<template>
  <section class="section">
    <div class="container">
      <AdminNav />
      <div class="toolbar">
        <h1>Услуги</h1>
        <button class="button" type="button" @click="editing = 'new'">Новая услуга</button>
      </div>
      <p class="muted lead">
        Услугу, по которой уже есть заказы, удалить нельзя — деактивируйте её: она исчезнет из каталога,
        а сделанные заказы останутся. Изменение цены уже оформленные заказы не меняет.
      </p>

      <p v-if="actionError" class="notice notice--error">{{ actionError }}</p>
      <p v-if="error && error.statusCode !== 401" class="notice notice--error">
        Не удалось загрузить услуги. Обновите страницу через минуту.
      </p>

      <div v-else-if="data && data.length" class="card table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Услуга</th>
              <th>Категория</th>
              <th>Цена</th>
              <th>Порядок</th>
              <th>Состояние</th>
              <th>Заказов</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="service in data" :key="service.id">
              <td data-label="Услуга">
                <strong>{{ service.title }}</strong><br>
                <span class="muted">{{ service.slug }}</span>
              </td>
              <td data-label="Категория">{{ CATEGORY_LABELS[service.category] }}</td>
              <td data-label="Цена" class="nowrap">{{ servicePriceLabel(service) }}</td>
              <td data-label="Порядок">{{ service.sort_order }}</td>
              <td data-label="Состояние">{{ service.is_active ? 'В каталоге' : 'Отключена' }}</td>
              <td data-label="Заказов">{{ service.orders_count }}</td>
              <td class="actions">
                <button class="link-button" type="button" @click="editing = service">Изменить</button>
                <button class="link-button" type="button" @click="toggle(service)">
                  {{ service.is_active ? 'Деактивировать' : 'Включить' }}
                </button>
                <button v-if="service.orders_count === 0" class="link-button" type="button" @click="remove(service)">
                  Удалить
                </button>
                <span v-else class="muted hint">Удалить нельзя: есть заказы</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="data" class="card empty">
        <p>Услуг пока нет. Создайте первую кнопкой «Новая услуга».</p>
      </div>
    </div>

    <ServiceFormDialog
      v-if="editing"
      :service="editing === 'new' ? undefined : editing"
      @close="editing = null"
      @done="onSaved"
      @unauthorized="toLogin"
    />
  </section>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-1);
}

.toolbar h1 {
  margin: 0;
}

.lead {
  margin: 0 0 var(--space-2);
  font-size: 0.92rem;
}

.hint {
  font-size: 0.85rem;
}
</style>
