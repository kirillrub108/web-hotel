<script setup lang="ts">
import type { Hotel } from '~/types'

const { data: hotel } = await useFetch<Hotel>('/api/hotel', { key: 'hotel' })

useHead({ title: 'Контакты — Kivana' })
</script>

<template>
  <section class="section">
    <div class="container">
      <h1>Контакты</h1>
      <p class="section__lead">
        Звоните в любое время: стойка размещения работает круглосуточно.
        На письма отвечаем в рабочие часы.
      </p>

      <div v-if="hotel" class="layout">
        <div class="card block">
          <h2>Как связаться</h2>
          <dl>
            <dt>Телефон</dt>
            <dd><a :href="'tel:' + hotel.phone.replace(/[^+\d]/g, '')">{{ hotel.phone }}</a></dd>
            <dt>Почта</dt>
            <dd><a :href="'mailto:' + hotel.email">{{ hotel.email }}</a></dd>
            <dt>Адрес</dt>
            <dd>{{ hotel.address }}</dd>
          </dl>
        </div>

        <div class="card block">
          <h2>Заезд и выезд</h2>
          <dl>
            <dt>Заезд</dt>
            <dd>с {{ hotel.check_in_time }}</dd>
            <dt>Выезд</dt>
            <dd>до {{ hotel.check_out_time }}</dd>
          </dl>
          <p class="note">
            Ранний заезд и поздний выезд — по договорённости, если номер свободен.
            Напишите об этом в комментарии к заявке.
          </p>
        </div>

        <div class="card block">
          <h2>Как добраться</h2>
          <p>
            От железнодорожного вокзала — троллейбус до остановки «Красная площадь»,
            дальше пять минут пешком вдоль набережной.
          </p>
          <p>
            На машине заезжайте со стороны Волжской набережной: ворота во двор
            открывает администратор, парковка бесплатная для гостей.
          </p>
        </div>
      </div>

      <p v-else class="notice notice--error">
        Не удалось загрузить контакты. Обновите страницу через минуту.
      </p>

      <p class="cta">
        <NuxtLink class="button" to="/rooms">Выбрать номер</NuxtLink>
      </p>
    </div>
  </section>
</template>

<style scoped>
.layout {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr));
}

.block {
  padding: var(--space-3);
}

dl {
  margin: 0;
}

dt {
  color: var(--muted);
  font-size: 0.9rem;
}

dd {
  margin: 0 0 var(--space-2);
  font-size: 1.1rem;
  font-weight: 600;
}

.note {
  color: var(--muted);
  font-size: 0.95rem;
  margin: var(--space-2) 0 0;
}

.cta {
  margin-top: var(--space-4);
}
</style>
