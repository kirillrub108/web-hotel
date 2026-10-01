<script setup lang="ts">
import type { Room } from '~/types'

const route = useRoute()
const slug = route.params.slug as string
const { user } = useCurrentUser()

const { data: room, error } = await useFetch<Room>('/api/rooms/' + slug)

if (!room.value) {
  throw error.value?.statusCode === 404
    ? createError({ statusCode: 404, message: 'Номер не найден', fatal: true })
    : createError({ statusCode: 503, message: 'Сайт временно недоступен', fatal: true })
}

useHead({ title: room.value.name + ' — Kivana' })

// Липкая кнопка «Забронировать» нужна на телефоне, пока форма брони и подвал вне экрана.
const aside = ref<HTMLElement | null>(null)
const isAsideVisible = ref(false)
const isFooterVisible = ref(false)
const showStickyCta = computed(() => room.value?.is_available && !isAsideVisible.value && !isFooterVisible.value)

onMounted(() => {
  const observe = (el: Element | null | undefined, flag: Ref<boolean>) => {
    if (!el) return
    new IntersectionObserver(([entry]) => (flag.value = Boolean(entry?.isIntersecting))).observe(el)
  }
  observe(aside.value, isAsideVisible)
  observe(document.querySelector('footer'), isFooterVisible)
})
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

        <aside id="booking" ref="aside" class="aside">
          <div v-if="!room.is_available" class="card gate">
            <h2>Номер недоступен</h2>
            <p>Мы подберём похожий вариант на ваши даты.</p>
            <NuxtLink class="button" to="/rooms">Смотреть другие номера</NuxtLink>
          </div>

          <div v-else-if="!user" class="card gate">
            <h2>Бронирование</h2>
            <p>Бронь и её статус будут в личном кабинете, а письма о решении придут на вашу почту.</p>
            <NuxtLink class="button" :to="{ path: '/login', query: { next: route.fullPath } }">
              Войдите, чтобы забронировать
            </NuxtLink>
            <p class="gate__note">Нет аккаунта? <NuxtLink to="/register">Зарегистрируйтесь</NuxtLink></p>
          </div>

          <div v-else-if="!user.email_verified_at" class="card gate">
            <h2>Подтвердите email</h2>
            <p>
              Бронировать можно после подтверждения почты. Ссылку мы отправили на {{ user.email }};
              отправить письмо ещё раз можно в личном кабинете.
            </p>
            <NuxtLink class="button button--ghost" to="/account">В личный кабинет</NuxtLink>
          </div>

          <BookingForm v-else :room="room" />
        </aside>
      </div>
    </div>

    <div class="cta" :class="{ 'cta--visible': showStickyCta }">
      <p class="cta__price">
        {{ room.price_per_night.toLocaleString('ru-RU') }} ₽
        <span class="cta__night">за ночь</span>
      </p>
      <a class="button" href="#booking">Забронировать</a>
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
  gap: var(--space-3);
  grid-template-columns: minmax(0, 1fr);
  align-items: start;
}

.photo {
  width: 100%;
  height: 220px;
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
  scroll-margin-top: 80px;
}

.gate {
  padding: var(--space-2);
}

.gate__note {
  margin-bottom: 0;
  color: var(--muted);
  font-size: 0.92rem;
}

/* Липкая кнопка: только на телефоне и планшете, поверх подвала не лежит (скрывается при его появлении). */
.cta {
  position: fixed;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 9;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-1) max(var(--space-2), var(--safe-right)) calc(var(--space-1) + var(--safe-bottom))
    max(var(--space-2), var(--safe-left));
  border-top: 1px solid var(--border);
  background: var(--surface);
  box-shadow: 0 -4px 16px rgba(60, 40, 25, 0.1);
  transform: translateY(100%);
  visibility: hidden;
  transition: transform 0.2s ease, visibility 0.2s;
}

.cta--visible {
  transform: none;
  visibility: visible;
}

.cta__price {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  line-height: 1.3;
}

.cta__night {
  display: block;
  color: var(--muted);
  font-size: 0.8rem;
  font-weight: 400;
}

@media (prefers-reduced-motion: reduce) {
  .cta {
    transition: none;
  }
}

@media (min-width: 640px) {
  .photo {
    height: 300px;
  }

  .gate {
    padding: var(--space-3);
  }
}

@media (min-width: 1024px) {
  .layout {
    gap: var(--space-4);
    grid-template-columns: 1.4fr 1fr;
  }

  .photo {
    height: 360px;
  }

  .aside {
    position: sticky;
    top: 90px;
  }

  .cta {
    display: none;
  }
}
</style>
