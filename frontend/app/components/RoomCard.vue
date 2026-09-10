<script setup lang="ts">
import type { Room } from '~/types'

defineProps<{ room: Room }>()
</script>

<template>
  <article class="card room">
    <NuxtLink :to="'/rooms/' + room.slug" class="room__image">
      <img :src="room.image" :alt="room.name" width="600" height="400">
    </NuxtLink>

    <div class="room__body">
      <h3>{{ room.name }}</h3>
      <p class="room__meta">
        до {{ room.capacity }} гостей · {{ room.area }} м²
      </p>
      <p class="room__description">{{ room.description }}</p>

      <div class="room__footer">
        <span class="room__price">
          {{ room.price_per_night.toLocaleString('ru-RU') }} ₽
          <span class="room__night">за ночь</span>
        </span>
        <NuxtLink class="button" :to="'/rooms/' + room.slug">Подробнее</NuxtLink>
      </div>
    </div>
  </article>
</template>

<style scoped>
.room {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.room__image img {
  width: 100%;
  height: 220px;
  object-fit: cover;
}

.room__body {
  display: flex;
  flex-direction: column;
  flex: 1;
  padding: var(--space-3);
}

.room__meta {
  color: var(--muted);
  font-size: 0.9rem;
}

.room__description {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  color: var(--muted);
  font-size: 0.95rem;
}

.room__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-top: auto;
  padding-top: var(--space-2);
}

.room__price {
  font-size: 1.15rem;
  font-weight: 700;
}

.room__night {
  display: block;
  color: var(--muted);
  font-size: 0.85rem;
  font-weight: 400;
}
</style>
