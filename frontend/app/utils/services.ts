import type {
  AdminService,
  HousekeepingKind,
  HousekeepingSlot,
  HousekeepingStatus,
  OrderStatus,
  Service,
  ServiceCategory,
  ServiceForm,
  ServiceUnit,
} from '~/types'

// Порядок категорий — порядок блоков на странице услуг.
export const CATEGORY_LABELS: Record<ServiceCategory, string> = {
  food: 'Еда и напитки в номер',
  housekeeping: 'Уборка и бельё',
  transfer: 'Трансфер',
  wellness: 'SPA и отдых',
  other: 'Другое',
}

export const UNIT_LABELS: Record<ServiceUnit, string> = {
  per_item: 'за штуку',
  per_stay: 'за проживание',
}

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  new: 'Новый',
  accepted: 'Принят',
  done: 'Выполнен',
  cancelled: 'Отменён',
}

export const SLOT_LABELS: Record<HousekeepingSlot, string> = {
  morning: 'Утро, 09:00–12:00',
  day: 'День, 12:00–15:00',
  evening: 'Вечер, 15:00–18:00',
  dnd: 'Не беспокоить',
}

export const KIND_LABELS: Record<HousekeepingKind, string> = {
  daily: 'Ежедневная уборка',
  checkout: 'Уборка после выезда',
}

export const TASK_STATUS_LABELS: Record<HousekeepingStatus, string> = {
  planned: 'Запланирована',
  done: 'Выполнена',
  skipped: 'Пропущена',
}

// «650 ₽ за штуку»
export function servicePriceLabel(service: Pick<Service, 'price' | 'unit'>): string {
  return `${formatRubles(service.price)} ${UNIT_LABELS[service.unit]}`
}

export interface ServiceGroup {
  category: ServiceCategory
  title: string
  services: Service[]
}

// Услуги по категориям в порядке CATEGORY_LABELS; пустые категории пропускаются. Порядок внутри группы — как пришёл с API.
export function groupServices(services: Service[]): ServiceGroup[] {
  return (Object.keys(CATEGORY_LABELS) as ServiceCategory[])
    .map(category => ({
      category,
      title: CATEGORY_LABELS[category],
      services: services.filter(service => service.category === category),
    }))
    .filter(group => group.services.length > 0)
}

// Полное тело изменения услуги: PATCH принимает все поля сразу.
export function serviceToForm(service: AdminService): ServiceForm {
  return {
    slug: service.slug,
    title: service.title,
    description: service.description,
    category: service.category,
    price: service.price,
    unit: service.unit,
    is_active: service.is_active,
    sort_order: service.sort_order,
  }
}

// Деактивация и повторное включение. Уже сделанные заказы не меняются.
export async function setServiceActive(service: AdminService, isActive: boolean): Promise<void> {
  await $fetch(`/api/admin/services/${service.id}`, {
    method: 'PATCH',
    body: { ...serviceToForm(service), is_active: isActive },
  })
}

// Значение для поля datetime-local из времени с поясом отеля, которое отдаёт API:
// «2026-10-02T14:00:00+03:00» уже записано по часам отеля, поэтому достаточно отрезать секунды и пояс.
export function toLocalInput(hotelDateTime: string): string {
  return hotelDateTime.slice(0, 16)
}
