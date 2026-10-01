<script setup lang="ts">
import type { BookingDetail, HousekeepingSlot, HousekeepingTask } from '~/types'

// Предпочтения по уборке по датам. Менять можно ежедневную уборку на дату позже сегодняшней:
// на сегодня она уже в работе, а после выезда время выбирать не нужно.
defineProps<{ detail: BookingDetail }>()
const emit = defineEmits<{ updated: [detail: BookingDetail] }>()

const SLOTS = Object.keys(SLOT_LABELS) as HousekeepingSlot[]

const error = ref('')
const savingId = ref<number | null>(null)

async function changeSlot(task: HousekeepingTask, event: Event): Promise<void> {
  const select = event.target as HTMLSelectElement
  error.value = ''
  savingId.value = task.id
  try {
    emit('updated', await $fetch<BookingDetail>(`/api/account/housekeeping/${task.id}`, {
      method: 'PATCH',
      body: { slot: select.value },
    }))
  }
  catch (err) {
    // Список остаётся прежним, поэтому возвращаем в поле выбранное ранее значение.
    select.value = task.slot
    error.value = apiErrorMessage(err, 'Не удалось сохранить время уборки. Попробуйте ещё раз.')
  }
  finally {
    savingId.value = null
  }
}
</script>

<template>
  <div>
    <ul class="tasks">
      <li v-for="task in detail.housekeeping" :key="task.id" class="tasks__item">
        <div>
          <strong>{{ formatDate(task.date) }}</strong>
          <span class="muted"> · {{ KIND_LABELS[task.kind] }}</span>
        </div>
        <select
          v-if="task.can_change_slot"
          :value="task.slot"
          :disabled="savingId === task.id"
          :aria-label="`Время уборки ${formatDate(task.date)}`"
          @change="changeSlot(task, $event)"
        >
          <option v-for="slot in SLOTS" :key="slot" :value="slot">{{ SLOT_LABELS[slot] }}</option>
        </select>
        <span v-else-if="task.kind === 'daily'" class="tasks__fixed">
          {{ SLOT_LABELS[task.slot] }}
          <StateBadge v-if="task.status !== 'planned'" :status="task.status" :label="TASK_STATUS_LABELS[task.status]" />
        </span>
        <StateBadge v-else-if="task.status !== 'planned'" :status="task.status" :label="TASK_STATUS_LABELS[task.status]" />
      </li>
    </ul>
    <p v-if="error" class="notice notice--error">{{ error }}</p>
  </div>
</template>

<style scoped>
.tasks {
  margin: 0 0 var(--space-1);
  padding: 0;
  list-style: none;
}

.tasks__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.tasks__item:last-child {
  border-bottom: 0;
}

.tasks__item select {
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font: inherit;
}

@media (max-width: 1023.98px) {
  .tasks__item select {
    min-height: var(--tap);
  }
}

.tasks__fixed {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
</style>
