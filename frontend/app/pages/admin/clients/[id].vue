<script setup lang="ts">
import type { AdminPromo, Client, ClientDetail, CrmStatus, Room } from '~/types'

const route = useRoute()
const clientId = Number(route.params.id)
const { clear } = useCurrentUser()

async function toLogin(): Promise<void> {
  clear()
  await navigateTo({ path: '/login', query: { next: route.fullPath } })
}

const { data, error, refresh } = await useFetch<ClientDetail>(`/api/admin/clients/${clientId}`)
const { data: rooms } = await useFetch<Room[]>('/api/rooms', { default: () => [] })

if (error.value?.statusCode === 401) {
  await toLogin()
}

const today = hotelToday()

// Форма CRM: черновик отдельно от данных страницы, чтобы не терять правки при перезагрузке списков ниже.
const crmStatus = ref<CrmStatus>(data.value?.client.crm_status ?? 'regular')
const crmNote = ref(data.value?.client.crm_note ?? '')
const crmSaving = ref(false)
const crmError = ref('')
const crmSaved = ref(false)

async function saveCrm(): Promise<void> {
  crmError.value = ''
  crmSaved.value = false
  crmSaving.value = true
  try {
    const fresh = await $fetch<Client>(`/api/admin/clients/${clientId}`, {
      method: 'PATCH',
      body: { crm_status: crmStatus.value, crm_note: crmNote.value },
    })
    crmStatus.value = fresh.crm_status
    crmNote.value = fresh.crm_note ?? ''
    crmSaved.value = true
    await refresh()
  }
  catch (err) {
    if ((err as { statusCode?: number }).statusCode === 401) {
      await toLogin()
      return
    }
    crmError.value = apiErrorMessage(err, 'Не удалось сохранить. Попробуйте ещё раз.')
  }
  finally {
    crmSaving.value = false
  }
}

const issuing = ref(false)
const promoError = ref('')

async function onPromoIssued(): Promise<void> {
  issuing.value = false
  await refresh()
}

async function togglePromo(promo: AdminPromo): Promise<void> {
  promoError.value = ''
  try {
    await setPromoActive(promo, !promo.is_active)
    await refresh()
  }
  catch (err) {
    if ((err as { statusCode?: number }).statusCode === 401) {
      await toLogin()
      return
    }
    promoError.value = apiErrorMessage(err, 'Не удалось изменить акцию')
  }
}

useHead({
  title: computed(() => `${data.value?.client.full_name ?? 'Клиент'} — Kivana`),
  meta: [{ name: 'robots', content: 'noindex' }],
})
</script>

<template>
  <section class="section">
    <div class="container">
      <AdminNav />

      <p v-if="error && error.statusCode !== 401" class="notice notice--error">
        {{ error.statusCode === 404 ? 'Клиент не найден.' : 'Не удалось загрузить клиента. Обновите страницу.' }}
        <NuxtLink to="/admin/clients">К списку клиентов</NuxtLink>
      </p>

      <template v-else-if="data">
        <p class="crumbs"><NuxtLink to="/admin/clients">Клиенты</NuxtLink> / {{ data.client.full_name }}</p>
        <h1>
          {{ data.client.full_name }}
          <span class="tag">{{ SEGMENT_LABELS[data.client.segment] }}</span>
          <span v-if="data.client.crm_status !== 'regular'" class="tag" :class="`crm--${data.client.crm_status}`">
            {{ CRM_LABELS[data.client.crm_status] }}
          </span>
        </h1>

        <div class="top">
          <div class="card block">
            <h2>Профиль и показатели</h2>
            <dl class="facts">
              <dt>Email</dt>
              <dd><a :href="`mailto:${data.client.email}`">{{ data.client.email }}</a></dd>
              <dt>Телефон</dt>
              <dd>{{ data.client.phone || 'не указан' }}</dd>
              <dt>Регистрация</dt>
              <dd>{{ formatDateTime(data.client.created_at) }}</dd>
              <dt>Активность</dt>
              <dd>{{ formatDateTime(data.client.last_activity_at) }}</dd>
              <dt>Проживаний</dt>
              <dd>{{ data.client.stays }}, ночей: {{ data.client.nights }}</dd>
              <dt>Выручка</dt>
              <dd>{{ formatRubles(data.client.revenue) }} <span class="muted">по подтверждённым броням</span></dd>
              <dt>Последнее проживание</dt>
              <dd>{{ data.client.last_stay_at ? formatDate(data.client.last_stay_at) : 'ещё не было' }}</dd>
            </dl>
          </div>

          <form class="card block" novalidate @submit.prevent="saveCrm">
            <h2>Статус и заметка</h2>
            <div class="field">
              <label for="crm-status">Статус клиента</label>
              <select id="crm-status" v-model="crmStatus">
                <option v-for="(label, value) in CRM_LABELS" :key="value" :value="value">{{ label }}</option>
              </select>
              <span class="muted hint">
                VIP: заявки с длинным проживанием, большой суммой и дальним заездом не требуют ручной проверки.
                Заблокированному клиенту новые заявки отклоняются автоматически.
              </span>
              <span v-if="crmStatus === 'blocked'" class="muted hint">
                Блокировка не отменяет существующие брони клиента — решайте по ним сами в разделе «Заявки».
              </span>
            </div>
            <div class="field">
              <label for="crm-note">Заметка</label>
              <textarea id="crm-note" v-model="crmNote" rows="4" maxlength="2000" />
              <span class="muted hint">Видна только администраторам.</span>
            </div>
            <p v-if="crmError" class="notice notice--error">{{ crmError }}</p>
            <p v-if="crmSaved" class="notice notice--success" aria-live="polite">Сохранено.</p>
            <button class="button" type="submit" :disabled="crmSaving">{{ crmSaving ? 'Сохраняем…' : 'Сохранить' }}</button>
          </form>
        </div>

        <h2 class="heading">Брони клиента</h2>
        <div v-if="data.bookings.length" class="card table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Бронь</th>
                <th>Номер</th>
                <th>Даты</th>
                <th>Сумма</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr v-for="booking in data.bookings" :key="booking.id">
                <td class="nowrap">№{{ booking.id }}<br><span class="muted">{{ formatDateTime(booking.created_at) }}</span></td>
                <td>{{ booking.room.name }}</td>
                <td class="nowrap">
                  {{ formatDate(booking.check_in) }} — {{ formatDate(booking.check_out) }}<br>
                  <span class="muted">{{ nightsLabel(booking.nights) }}</span>
                </td>
                <td class="nowrap">
                  {{ formatRubles(booking.total_price) }}
                  <template v-if="booking.promo">
                    <br><span class="muted">−{{ formatRubles(booking.discount) }}, {{ booking.promo.code }}</span>
                  </template>
                </td>
                <td><StatusBadge :status="booking.display_status" /></td>
                <td><NuxtLink :to="{ path: '/admin', query: { status: booking.status } }">В заявках</NuxtLink></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="card empty"><p>У клиента ещё нет броней.</p></div>

        <div class="heading heading--row">
          <h2>Акции клиента</h2>
          <button class="button button--small" type="button" @click="issuing = true">Выдать персональную акцию</button>
        </div>
        <p v-if="promoError" class="notice notice--error">{{ promoError }}</p>
        <div v-if="data.promos.length" class="card table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Код</th>
                <th>Акция</th>
                <th>Условия</th>
                <th>Состояние</th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr v-for="promo in data.promos" :key="promo.id">
                <td class="nowrap"><strong>{{ promo.code }}</strong></td>
                <td>{{ promo.title }}<br><span class="muted">{{ promoValueLabel(promo) }}</span></td>
                <td>
                  <ul class="conditions">
                    <li v-for="condition in promoConditions(promo)" :key="condition">{{ condition }}</li>
                  </ul>
                </td>
                <td>{{ promoStateLabel(promo, today) }}</td>
                <td>
                  <button class="link-button" type="button" @click="togglePromo(promo)">
                    {{ promo.is_active ? 'Деактивировать' : 'Включить' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="card empty"><p>Персональных акций у клиента нет.</p></div>
      </template>
    </div>

    <PromoFormDialog
      v-if="issuing && data"
      :rooms="rooms ?? []"
      :client="{ id: data.client.id, full_name: data.client.full_name }"
      @close="issuing = false"
      @done="onPromoIssued"
      @unauthorized="toLogin"
    />
  </section>
</template>

<style scoped>
.crumbs {
  margin: 0 0 var(--space-1);
  color: var(--muted);
}

h1 .tag {
  margin-left: 6px;
  vertical-align: middle;
}

.crm--vip {
  background: #e7f3ec;
  color: var(--success);
}

.crm--blocked {
  background: #f8e9e7;
  color: var(--danger);
}

.top {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  align-items: start;
}

.block {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
}

.block h2 {
  margin: 0;
}

.facts {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 8px var(--space-2);
  margin: 0;
}

.facts dt {
  color: var(--muted);
}

.facts dd {
  margin: 0;
}

.hint {
  font-size: 0.85rem;
}

.heading {
  margin: var(--space-4) 0 var(--space-2);
}

.heading--row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.heading--row h2 {
  margin: 0;
}

.conditions {
  margin: 0;
  padding-left: 18px;
}
</style>
