<script setup lang="ts">
import type { Hotel } from '~/types'

const { data: hotel } = await useFetch<Hotel>('/api/hotel', { key: 'hotel' })
</script>

<template>
  <footer class="footer">
    <div class="container footer__inner">
      <div>
        <p class="footer__title">{{ hotel?.name ?? 'Kivana' }}</p>
        <p class="footer__muted">{{ hotel?.tagline }}</p>
      </div>

      <div v-if="hotel">
        <p class="footer__muted">{{ hotel.address }}</p>
        <p>
          <a :href="'tel:' + hotel.phone.replace(/[^+\d]/g, '')">{{ hotel.phone }}</a>
        </p>
        <p>
          <a :href="'mailto:' + hotel.email">{{ hotel.email }}</a>
        </p>
      </div>

      <div v-if="hotel">
        <p class="footer__muted">Заезд с {{ hotel.check_in_time }}</p>
        <p class="footer__muted">Выезд до {{ hotel.check_out_time }}</p>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  margin-top: var(--space-5);
  padding: var(--space-4) 0;
  background: var(--text);
  color: var(--surface-warm);
}

.footer__inner {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.footer__title {
  font-size: 1.15rem;
  font-weight: 700;
  margin-bottom: 4px;
}

.footer__muted {
  color: #c8b8aa;
  margin-bottom: 4px;
}

.footer a {
  color: var(--surface-warm);
}

.footer p {
  margin-bottom: 4px;
}
</style>
