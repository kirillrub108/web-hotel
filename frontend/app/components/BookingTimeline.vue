<script setup lang="ts">
import type { BookingEvent } from '~/types'

defineProps<{ events: BookingEvent[] }>()

function title(event: BookingEvent): string {
  return event.from_status === null ? 'Заявка создана' : STATUS_LABELS[event.to_status]
}
</script>

<template>
  <ol class="timeline">
    <li v-for="event in events" :key="event.id" class="timeline__item">
      <p class="timeline__title">{{ title(event) }}</p>
      <p class="timeline__meta">{{ ACTOR_LABELS[event.actor] }} · {{ formatDateTime(event.created_at) }}</p>
      <ul v-if="event.reasons.length" class="timeline__reasons">
        <li v-for="reason in event.reasons" :key="reason">{{ reason }}</li>
      </ul>
    </li>
  </ol>
</template>

<style scoped>
.timeline {
  margin: 0;
  padding: 0;
  list-style: none;
}

.timeline__item {
  position: relative;
  padding: 0 0 var(--space-2) var(--space-3);
  border-left: 2px solid var(--border);
}

.timeline__item:last-child {
  padding-bottom: 0;
  border-left-color: transparent;
}

.timeline__item::before {
  content: '';
  position: absolute;
  top: 4px;
  left: -7px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--accent);
}

.timeline__title {
  margin: 0;
  font-weight: 600;
}

.timeline__meta {
  margin: 2px 0 0;
  color: var(--muted);
  font-size: 0.88rem;
}

.timeline__reasons {
  margin: 6px 0 0;
  padding-left: 18px;
  font-size: 0.92rem;
}
</style>
