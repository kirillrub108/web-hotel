<script setup lang="ts">
import type { DisplayStatus } from '~/types'

defineProps<{ status: DisplayStatus }>()
</script>

<template>
  <span class="status" :class="`status--${status}`">{{ STATUS_LABELS[status] }}</span>
</template>

<style scoped>
.status {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 600;
  white-space: nowrap;
}

.status--pending {
  background: var(--surface-warm);
  color: var(--accent-dark);
}

.status--confirmed,
.status--in_stay {
  background: #e7f3ec;
  color: var(--success);
}

.status--in_stay {
  box-shadow: inset 0 0 0 1px var(--success);
}

.status--declined {
  background: #f8e9e7;
  color: var(--danger);
}

.status--completed,
.status--cancelled {
  background: #f1eeec;
  color: var(--muted);
}
</style>
