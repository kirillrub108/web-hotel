<script setup lang="ts">
import type { AdminHousekeepingTask, HousekeepingStatus } from '~/types'

// Строка расписания уборки: номер, гость и отметка администратора.
defineProps<{ task: AdminHousekeepingTask, busy: boolean }>()
const emit = defineEmits<{ mark: [status: HousekeepingStatus] }>()
</script>

<template>
  <li class="row">
    <div class="row__info">
      <strong>{{ task.room.name }}</strong>
      <span v-if="task.arrival_today" class="row__flag">Заезд сегодня</span>
      <p class="muted row__guest">{{ task.booking.guest_name }}, {{ task.booking.phone }} · бронь №{{ task.booking.id }}</p>
    </div>
    <div class="row__actions">
      <StateBadge :status="task.status" :label="TASK_STATUS_LABELS[task.status]" />
      <button
        class="button button--small"
        :class="{ 'button--ghost': task.status !== 'done' }"
        type="button"
        :disabled="busy || task.status === 'done'"
        @click="emit('mark', 'done')"
      >
        Выполнено
      </button>
      <button
        class="button button--small button--ghost"
        type="button"
        :disabled="busy || task.status === 'skipped'"
        @click="emit('mark', 'skipped')"
      >
        Пропущено
      </button>
    </div>
  </li>
</template>

<style scoped>
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding: 12px var(--space-2);
  border-bottom: 1px solid var(--border);
}

.row:last-child {
  border-bottom: 0;
}

.row__guest {
  margin: 0;
  font-size: 0.88rem;
}

.row__flag {
  margin-left: var(--space-1);
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
}

.row__actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-wrap: wrap;
}

@media (max-width: 639.98px) {
  .row__actions .button {
    flex: 1 1 40%;
  }
}
</style>
