<script setup lang="ts">
import type { ClientPage } from '~/types'

const PAGE_SIZE = 20

const { clear } = useCurrentUser()

const searchInput = ref('')
// Поиск запускается кнопкой или Enter, а не на каждую букву: лишних запросов нет.
const search = ref('')
const page = ref(0)

const query = computed(() => ({
  limit: PAGE_SIZE,
  offset: page.value * PAGE_SIZE,
  ...(search.value ? { search: search.value } : {}),
}))

const { data, error } = await useFetch<ClientPage>('/api/admin/clients', { query })

if (error.value?.statusCode === 401) {
  clear()
  await navigateTo({ path: '/login', query: { next: '/admin/clients' } })
}

const total = computed(() => data.value?.total ?? 0)
const hasNextPage = computed(() => (page.value + 1) * PAGE_SIZE < total.value)

function applySearch(): void {
  page.value = 0
  search.value = searchInput.value.trim()
}

function resetSearch(): void {
  searchInput.value = ''
  applySearch()
}

useHead({
  title: 'Клиенты — Kivana',
  meta: [{ name: 'robots', content: 'noindex' }],
})
</script>

<template>
  <section class="section">
    <div class="container">
      <AdminNav />
      <h1>Клиенты</h1>

      <form class="search" role="search" @submit.prevent="applySearch">
        <label class="search__label" for="client-search">Поиск по имени, email или телефону</label>
        <div class="search__row">
          <input id="client-search" v-model="searchInput" type="search" inputmode="search" enterkeyhint="search" maxlength="100" placeholder="Анна, ivan@example.com, 900 123">
          <button class="button" type="submit">Найти</button>
          <button v-if="search" class="button button--ghost" type="button" @click="resetSearch">Сбросить</button>
        </div>
      </form>

      <p v-if="error && error.statusCode !== 401" class="notice notice--error">
        Не удалось загрузить клиентов. Обновите страницу через минуту.
      </p>

      <div v-else-if="data && data.items.length" class="card table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Клиент</th>
              <th>Сегмент</th>
              <th>Проживаний</th>
              <th>Ночей</th>
              <th>Выручка</th>
              <th>Последнее проживание</th>
              <th>Активность</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="client in data.items" :key="client.id">
              <td data-label="Клиент">
                <NuxtLink :to="`/admin/clients/${client.id}`"><strong>{{ client.full_name }}</strong></NuxtLink><br>
                <span class="muted">{{ client.email }}</span>
                <template v-if="client.phone">
                  <br><span class="muted">{{ client.phone }}</span>
                </template>
              </td>
              <td data-label="Сегмент">
                <span class="tag">{{ SEGMENT_LABELS[client.segment] }}</span>
                <span v-if="client.crm_status !== 'regular'" class="tag crm" :class="`crm--${client.crm_status}`">
                  {{ CRM_LABELS[client.crm_status] }}
                </span>
              </td>
              <td data-label="Проживаний">{{ client.stays }}</td>
              <td data-label="Ночей">{{ client.nights }}</td>
              <td data-label="Выручка" class="nowrap">{{ formatRubles(client.revenue) }}</td>
              <td data-label="Последнее проживание" class="nowrap">{{ client.last_stay_at ? formatDate(client.last_stay_at) : '—' }}</td>
              <td data-label="Активность" class="nowrap">{{ formatDateTime(client.last_activity_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="data" class="card empty">
        <p v-if="search">По запросу «{{ search }}» никого не нашли.</p>
        <p v-else>Клиентов пока нет: они появятся после регистрации на сайте.</p>
      </div>

      <p v-if="data && data.items.length" class="muted note">Клиенты отсортированы по последней активности: входу или заявке.</p>

      <div v-if="total > PAGE_SIZE" class="pager">
        <button class="button button--ghost button--small" type="button" :disabled="page === 0" @click="page--">
          Назад
        </button>
        <span class="muted">
          {{ page * PAGE_SIZE + 1 }}–{{ Math.min((page + 1) * PAGE_SIZE, total) }} из {{ total }}
        </span>
        <button class="button button--ghost button--small" type="button" :disabled="!hasNextPage" @click="page++">
          Вперёд
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.search {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: var(--space-3);
}

.search__label {
  font-size: 0.9rem;
  font-weight: 600;
}

.search__row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.search__row input {
  flex: 1 1 100%;
  min-height: var(--tap);
  padding: 11px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font: inherit;
}

.search__row .button {
  flex: 1;
}

@media (min-width: 640px) {
  .search__row input {
    flex-basis: 260px;
  }

  .search__row .button {
    flex: none;
  }
}

.crm {
  margin-left: 6px;
}

.crm--vip {
  background: #e7f3ec;
  color: var(--success);
}

.crm--blocked {
  background: #f8e9e7;
  color: var(--danger);
}

.note {
  margin: var(--space-2) 0 0;
  font-size: 0.85rem;
}
</style>
