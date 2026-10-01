<script setup lang="ts">
import type { Room } from '~/types'

const route = useRoute()
const slug = route.params.slug as string

const { data: room, error } = await useFetch<Room>('/api/rooms/' + slug)

if (!room.value) {
  throw error.value?.statusCode === 404
    ? createError({ statusCode: 404, message: 'Номер не найден', fatal: true })
    : createError({ statusCode: 503, message: 'Сайт временно недоступен', fatal: true })
}

useHead({ title: room.value.name + ' — Kivana' })
</script>

<template>
  <section v-if="room" class="section">
    <div class="container">
      <p class="crumbs">
        <NuxtLink to="/rooms">Номера</NuxtLink> / {{ room.name }}
      </p>

      <div class="layout">
        <div>
          <img class="photo" :src="room.image" :alt="room.name" width="900" height="600">

          <h1>{{ room.name }}</h1>
          <p class="meta">
            <span class="tag">до {{ room.capacity }} гостей</span>
            <span class="tag">{{ room.area }} м²</span>
            <span class="tag">{{ room.price_per_night.toLocaleString('ru-RU') }} ₽ за ночь</span>
          </p>

          <p>{{ room.description }}</p>

          <h2>Что в номере</h2>
          <ul class="amenities">
            <li v-for="item in room.amenities" :key="item">{{ item }}</li>
          </ul>

          <p v-if="!room.is_available" class="notice notice--error">
            Номер временно снят с продажи. Выберите другой или позвоните нам.
          </p>
        </div>

        <aside class="aside">
          <BookingForm v-if="room.is_available" :room="room" />
          <div v-else class="card unavailable">
            <h2>Номер недоступен</h2>
            <p>Мы подберём похожий вариант на ваши даты.</p>
            <NuxtLink class="button" to="/rooms">Смотреть другие номера</NuxtLink>
          </div>
        </aside>
      </div>
    </div>
  </section>
</template>

<style scoped>
.crumbs {
  color: var(--muted);
  font-size: 0.9rem;
}

.layout {
  display: grid;
  gap: var(--space-4);
  grid-template-columns: 1.4fr 1fr;
  align-items: start;
}

.photo {
  width: 100%;
  height: 360px;
  object-fit: cover;
  border-radius: var(--radius);
  margin-bottom: var(--space-3);
}

.meta {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.amenities {
  display: grid;
  gap: var(--space-1);
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  padding-left: 20px;
  color: var(--muted);
}

.aside {
  position: sticky;
  top: 90px;
}

.unavailable {
  padding: var(--space-3);
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .aside {
    position: static;
  }
}
</style>
