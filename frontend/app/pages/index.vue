<script setup lang="ts">
import type { Hotel, Room, Service } from '~/types'

const { data: hotel } = await useFetch<Hotel>('/api/hotel', { key: 'hotel' })
const { data: rooms, error: roomsError } = await useFetch<Room[]>('/api/rooms', { key: 'rooms-all' })

const popular = computed(() => (rooms.value ?? []).slice(0, 3))

// На главной — по одной услуге из каждой категории; полный каталог на /services.
const { data: services } = await useFetch<Service[]>('/api/services', { key: 'services' })
const featured = computed(() =>
  groupServices(services.value ?? []).map(group => group.services[0]).filter((service): service is Service => service !== undefined),
)

useHead({ title: 'Kivana — гостиница в Ярославле' })
</script>

<template>
  <div>
    <section class="hero">
      <div class="container">
        <p class="hero__tag">Гостиница в центре Ярославля</p>
        <h1>{{ hotel?.name ?? 'Kivana' }}</h1>
        <p class="hero__tagline">{{ hotel?.tagline }}</p>
        <div class="hero__actions">
          <NuxtLink class="button" to="/rooms">Посмотреть номера</NuxtLink>
          <NuxtLink class="button button--ghost" to="/contacts">Как нас найти</NuxtLink>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container about">
        <div>
          <h2>О гостинице</h2>
          <p>{{ hotel?.description }}</p>
        </div>
        <ul v-if="hotel" class="about__facts card">
          <li>
            <span>Заезд</span>
            <strong>с {{ hotel.check_in_time }}</strong>
          </li>
          <li>
            <span>Выезд</span>
            <strong>до {{ hotel.check_out_time }}</strong>
          </li>
          <li>
            <span>Номеров</span>
            <strong>18</strong>
          </li>
          <li>
            <span>До набережной</span>
            <strong>2 минуты пешком</strong>
          </li>
        </ul>
      </div>
    </section>

    <section class="section section--warm">
      <div class="container">
        <h2>Популярные номера</h2>
        <p class="section__lead">Три варианта, которые чаще всего выбирают наши гости.</p>
        <p v-if="roomsError" class="notice notice--error">
          Не удалось загрузить номера. Обновите страницу через минуту.
        </p>
        <div v-else class="grid">
          <RoomCard v-for="room in popular" :key="room.id" :room="room" />
        </div>
        <p class="more">
          <NuxtLink class="button button--ghost" to="/rooms">Все номера</NuxtLink>
        </p>
      </div>
    </section>

    <section v-if="featured.length" class="section">
      <div class="container">
        <h2>Услуги</h2>
        <p class="section__lead">Заказывайте к подтверждённой брони в личном кабинете, оплата — на ресепшене.</p>
        <div class="grid">
          <div v-for="service in featured" :key="service.id" class="card service">
            <h3>{{ service.title }}</h3>
            <p>{{ service.description }}</p>
          </div>
        </div>
        <p class="more">
          <NuxtLink class="button button--ghost" to="/services">Все услуги</NuxtLink>
        </p>
      </div>
    </section>

    <section v-if="hotel" class="section section--warm">
      <div class="container contacts-short">
        <div>
          <h2>Забронировать по телефону</h2>
          <p>Если удобнее голосом — позвоните, администратор на стойке круглосуточно.</p>
        </div>
        <div class="contacts-short__data">
          <p><a :href="'tel:' + hotel.phone.replace(/[^+\d]/g, '')">{{ hotel.phone }}</a></p>
          <p><a :href="'mailto:' + hotel.email">{{ hotel.email }}</a></p>
          <p class="contacts-short__address">{{ hotel.address }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.hero {
  padding: var(--space-5) 0;
  background: linear-gradient(160deg, #f6ece1 0%, #efe0d0 100%);
}

.hero__tag {
  color: var(--accent-dark);
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-size: 0.85rem;
}

.hero__tagline {
  max-width: 46ch;
  font-size: 1.15rem;
  color: var(--muted);
}

.hero__actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-top: var(--space-3);
}

.about {
  display: grid;
  gap: var(--space-4);
  grid-template-columns: 1.6fr 1fr;
  align-items: start;
}

.about__facts {
  list-style: none;
  margin: 0;
  padding: var(--space-2) var(--space-3);
}

.about__facts li {
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}

.about__facts li:last-child {
  border-bottom: 0;
}

.about__facts span {
  color: var(--muted);
}

.service {
  padding: var(--space-3);
}

.service p {
  color: var(--muted);
  margin: 0;
}

.more {
  margin-top: var(--space-3);
}

.contacts-short {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: 1.6fr 1fr;
  align-items: center;
}

.contacts-short__data p {
  font-size: 1.15rem;
  font-weight: 600;
  margin-bottom: 4px;
}

.contacts-short__address {
  font-size: 1rem !important;
  font-weight: 400 !important;
  color: var(--muted);
}

@media (max-width: 800px) {
  .about,
  .contacts-short {
    grid-template-columns: 1fr;
  }
}
</style>
