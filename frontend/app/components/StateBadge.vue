<script setup lang="ts">
import type { HousekeepingStatus, OrderStatus } from '~/types'

// Бейдж заказа услуги или уборки. Подпись приходит снаружи: у заказа и уборки она разная («Выполнен» и «Выполнена»).
defineProps<{ status: OrderStatus | HousekeepingStatus, label: string }>()
</script>

<template>
  <span class="state" :class="`state--${status}`">{{ label }}</span>
</template>

<style scoped>
.state {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 600;
  white-space: nowrap;
}

.state--new,
.state--planned {
  background: var(--surface-warm);
  color: var(--accent-dark);
}

.state--accepted,
.state--done {
  background: #e7f3ec;
  color: var(--success);
}

.state--cancelled,
.state--skipped {
  background: #f1eeec;
  color: var(--muted);
}
</style>
