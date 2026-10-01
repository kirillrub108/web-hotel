<script setup lang="ts">
import type { AdminPromo, Room } from '~/types'

const { clear } = useCurrentUser()

async function toLogin(): Promise<void> {
  clear()
  await navigateTo({ path: '/login', query: { next: '/admin/promos' } })
}

// Фильтр: все акции, только общие или только персональные.
const TABS: { value: boolean | undefined, label: string }[] = [
  { value: undefined, label: 'Все' },
  { value: false, label: 'Общие' },
  { value: true, label: 'Персональные' },
]
const personal = ref<boolean | undefined>(undefined)
const query = computed(() => (personal.value === undefined ? {} : { personal: personal.value }))

const { data, error, refresh } = await useFetch<AdminPromo[]>('/api/admin/promos', { query })
const { data: rooms } = await useFetch<Room[]>('/api/rooms', { default: () => [] })

if (error.value?.statusCode === 401) {
  await toLogin()
}

const today = hotelToday()
const editing = ref<AdminPromo | 'new' | null>(null)
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

function toggle(promo: AdminPromo): Promise<void> {
  return runAction(() => setPromoActive(promo, !promo.is_active), 'Не удалось изменить акцию')
}

function remove(promo: AdminPromo): Promise<void> {
  if (!confirm(`Удалить акцию ${promo.code}? Это действие нельзя отменить.`)) {
    return Promise.resolve()
  }
  return runAction(
    async () => {
      await $fetch(`/api/admin/promos/${promo.id}`, { method: 'DELETE' })
    },
    'Не удалось удалить акцию',
  )
}

async function onSaved(): Promise<void> {
  editing.value = null
  await refresh()
}

useHead({
  title: 'Акции — Kivana',
  meta: [{ name: 'robots', content: 'noindex' }],
})
</script>

<template>
  <section class="section">
    <div class="container">
      <AdminNav />
      <div class="toolbar">
        <h1>Акции</h1>
        <button class="button" type="button" @click="editing = 'new'">Новая акция</button>
      </div>
      <p class="muted lead">
        Промокод одноразовый: после применения он занят, пока бронь на рассмотрении или подтверждена, и освобождается при отказе или отмене.
        Персональные акции выдаются и с карточки клиента.
      </p>

      <div class="tabs" role="tablist" aria-label="Вид акций">
        <button
          v-for="tab in TABS"
          :key="tab.label"
          class="tabs__item"
          :class="{ 'tabs__item--active': personal === tab.value }"
          type="button"
          role="tab"
          :aria-selected="personal === tab.value"
          @click="personal = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>

      <p v-if="actionError" class="notice notice--error">{{ actionError }}</p>
      <p v-if="error && error.statusCode !== 401" class="notice notice--error">
        Не удалось загрузить акции. Обновите страницу через минуту.
      </p>

      <div v-else-if="data && data.length" class="card table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Код</th>
              <th>Акция</th>
              <th>Для кого</th>
              <th>Условия</th>
              <th>Состояние</th>
              <th>Броней</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="promo in data" :key="promo.id">
              <td class="nowrap"><strong>{{ promo.code }}</strong></td>
              <td>
                {{ promo.title }}<br>
                <span class="muted">{{ promoValueLabel(promo) }}</span>
              </td>
              <td>
                <NuxtLink v-if="promo.user" :to="`/admin/clients/${promo.user.id}`">{{ promo.user.full_name }}</NuxtLink>
                <span v-else>Все клиенты</span>
              </td>
              <td>
                <ul class="conditions">
                  <li v-for="condition in promoConditions(promo)" :key="condition">{{ condition }}</li>
                </ul>
              </td>
              <td>{{ promoStateLabel(promo, today) }}</td>
              <td>{{ promo.bookings_count }}</td>
              <td class="actions">
                <button class="link-button" type="button" @click="editing = promo">Изменить</button>
                <button class="link-button" type="button" @click="toggle(promo)">
                  {{ promo.is_active ? 'Деактивировать' : 'Включить' }}
                </button>
                <button v-if="promo.bookings_count === 0" class="link-button" type="button" @click="remove(promo)">
                  Удалить
                </button>
                <span v-else class="muted hint">Удалить нельзя: есть брони</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="data" class="card empty">
        <p>Акций пока нет. Создайте первую кнопкой «Новая акция».</p>
      </div>
    </div>

    <PromoFormDialog
      v-if="editing"
      :rooms="rooms ?? []"
      :promo="editing === 'new' ? undefined : editing"
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

.conditions {
  margin: 0;
  padding-left: 18px;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.hint {
  font-size: 0.85rem;
}
</style>
