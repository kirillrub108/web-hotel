import type { Actor, CrmStatus, DisplayStatus, Segment } from '~/types'

// Единый словарь статусов брони: бейджи в форме, кабинете и админке берут подписи только отсюда.
export const STATUS_LABELS: Record<DisplayStatus, string> = {
  pending: 'На рассмотрении',
  confirmed: 'Подтверждена',
  in_stay: 'Проживание',
  completed: 'Завершена',
  declined: 'Отклонена',
  cancelled: 'Отменена',
}

export const ACTOR_LABELS: Record<Actor, string> = {
  system: 'Автоматически',
  admin: 'Администратор',
  guest: 'Гость',
}

export const CRM_LABELS: Record<CrmStatus, string> = {
  regular: 'Обычный клиент',
  vip: 'VIP',
  blocked: 'Заблокирован',
}

// Сегмент считает backend по числу завершённых проживаний: «Гость» — одно проживание.
export const SEGMENT_LABELS: Record<Segment, string> = {
  new: 'Новый',
  guest: 'Гость',
  regular: 'Постоянный',
}

// Совпадает с HOTEL_TZ backend. Пояс задан явно, чтобы сервер (UTC) и браузер показывали одно и то же время
// и гидратация не расходилась.
const HOTEL_TIME_ZONE = 'Europe/Moscow'

// «Сегодня» по часам отеля в формате YYYY-MM-DD — для подсказки min у полей дат; проверяет даты backend.
export function hotelToday(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: HOTEL_TIME_ZONE }).format(new Date())
}

export function formatDate(isoDate: string): string {
  return isoDate.split('-').reverse().join('.')
}

export function formatDateTime(isoDateTime: string): string {
  return new Date(isoDateTime).toLocaleString('ru-RU', {
    timeZone: HOTEL_TIME_ZONE,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatRubles(amount: number): string {
  return `${amount.toLocaleString('ru-RU')} ₽`
}

// 1 ночь, 2 ночи, 5 ночей, 21 ночь.
export function nightsLabel(count: number): string {
  const lastTwo = count % 100
  const last = count % 10
  if (last === 1 && lastTwo !== 11) {
    return `${count} ночь`
  }
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) {
    return `${count} ночи`
  }
  return `${count} ночей`
}
