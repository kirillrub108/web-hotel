export interface Hotel {
  id: number
  name: string
  tagline: string
  description: string
  address: string
  phone: string
  email: string
  check_in_time: string
  check_out_time: string
}

export interface Room {
  id: number
  slug: string
  name: string
  description: string
  price_per_night: number
  capacity: number
  area: number
  amenities: string[]
  image: string
  is_available: boolean
}

// Тело изменения номера админом: PATCH принимает все поля сразу.
export interface RoomForm {
  price_per_night: number
  description: string
  is_available: boolean
}

export type BookingStatus = 'pending' | 'confirmed' | 'declined' | 'cancelled'

// Статус для показа: «Проживание» и «Завершена» backend вычисляет из подтверждённой брони.
export type DisplayStatus = BookingStatus | 'in_stay' | 'completed'

export type Actor = 'system' | 'admin' | 'guest'

export type CrmStatus = 'regular' | 'vip' | 'blocked'

export type AdminAction = 'confirm' | 'decline' | 'cancel'

export type PromoKind = 'percent' | 'fixed'

export type Segment = 'new' | 'guest' | 'regular'

export interface PromoShort {
  code: string
  title: string
}

// Предложение клиенту: условия акции без служебных полей.
export interface Promo {
  id: number
  code: string
  title: string
  description: string
  kind: PromoKind
  value: number
  valid_from: string
  valid_to: string
  min_nights: number
  room_id: number | null
  room: { slug: string, name: string } | null
  is_personal: boolean
}

export interface AdminPromo extends Promo {
  is_active: boolean
  created_at: string
  user: { id: number, email: string, full_name: string, crm_status: CrmStatus } | null
  // Код занят бронью в статусе «На рассмотрении» или «Подтверждена».
  in_use: boolean
  bookings_count: number
}

// Тело создания и изменения акции. room_id и user_id: null — любой номер и общая акция.
export interface PromoForm {
  code: string
  title: string
  description: string
  kind: PromoKind
  value: number
  valid_from: string
  valid_to: string
  min_nights: number
  room_id: number | null
  user_id: number | null
  is_active: boolean
}

export interface Quote {
  available: boolean
  unavailable_reason: string | null
  nights: number
  price_per_night: number
  subtotal: number
  discount: number
  total: number
  promo_title: string | null
}

export interface Booking {
  id: number
  room: { slug: string, name: string }
  guest_name: string
  phone: string
  check_in: string
  check_out: string
  guests: number
  comment: string | null
  status: BookingStatus
  display_status: DisplayStatus
  nights: number
  price_per_night: number
  discount: number
  total_price: number
  promo: PromoShort | null
  // Причины последнего решения простыми словами.
  reasons: string[]
  created_at: string
  cancelled_at: string | null
}

export interface BookingEvent {
  id: number
  // null — событие создания заявки.
  from_status: BookingStatus | null
  to_status: BookingStatus
  actor: Actor
  reasons: string[]
  created_at: string
}

export interface BookingDetail {
  booking: Booking
  events: BookingEvent[]
  cancel_deadline: string | null
  can_cancel: boolean
  orders: GuestServiceOrder[]
  // Итог по заказам без отменённых; услуги оплачиваются на ресепшене.
  services_total: number
  can_order: boolean
  // Окно, в которое должно попасть время заказа: время отеля со смещением пояса, например 2026-10-02T14:00:00+03:00.
  order_window: { start: string, end: string } | null
  // Часы приёма заказов еды, например «08:00–23:00».
  room_service_hours: string
  housekeeping: HousekeepingTask[]
}

export interface AdminBooking extends Booking {
  reason_codes: string[]
  user: { id: number, email: string, full_name: string, crm_status: CrmStatus }
  decided_by: Actor | null
  cancelled_by: Actor | null
}

export interface AdminBookingDetail {
  booking: AdminBooking
  events: BookingEvent[]
}

export interface AdminBookingPage {
  items: AdminBooking[]
  total: number
}

export interface Client {
  id: number
  email: string
  full_name: string
  phone: string | null
  crm_status: CrmStatus
  crm_note: string | null
  created_at: string
  last_activity_at: string
  // Завершённые проживания и ночи в них; выручка — по всем подтверждённым броням.
  stays: number
  nights: number
  revenue: number
  last_stay_at: string | null
  segment: Segment
}

export interface ClientPage {
  items: Client[]
  total: number
}

export interface ClientDetail {
  client: Client
  bookings: AdminBooking[]
  promos: AdminPromo[]
}

export type UserRole = 'guest' | 'admin'

export interface CurrentUser {
  id: number
  email: string
  full_name: string
  phone: string | null
  role: UserRole
  email_verified_at: string | null
  created_at: string
}

export type ServiceCategory = 'food' | 'housekeeping' | 'transfer' | 'wellness' | 'other'

// per_item — цена за штуку, количество можно менять; per_stay — цена за всё проживание, заказ один.
export type ServiceUnit = 'per_item' | 'per_stay'

export interface Service {
  id: number
  slug: string
  title: string
  description: string
  category: ServiceCategory
  price: number
  unit: ServiceUnit
}

export interface AdminService extends Service {
  is_active: boolean
  sort_order: number
  orders_count: number
}

// Тело создания и изменения услуги: PATCH принимает все поля сразу.
export interface ServiceForm {
  slug: string
  title: string
  description: string
  category: ServiceCategory
  price: number
  unit: ServiceUnit
  is_active: boolean
  sort_order: number
}

export type OrderStatus = 'new' | 'accepted' | 'done' | 'cancelled'

export interface ServiceOrder {
  id: number
  // Услуга остаётся в заказе и после деактивации.
  service: { id: number, title: string, category: ServiceCategory, unit: ServiceUnit, is_active: boolean }
  quantity: number
  unit_price: number
  total: number
  scheduled_at: string
  comment: string | null
  status: OrderStatus
  created_at: string
}

export interface GuestServiceOrder extends ServiceOrder {
  can_cancel: boolean
}

export interface AdminServiceOrder extends ServiceOrder {
  booking: { id: number, guest_name: string, phone: string, room: { slug: string, name: string } }
}

export type HousekeepingKind = 'daily' | 'checkout'

// Слоты ежедневной уборки: утро 09–12, день 12–15, вечер 15–18 или «не беспокоить».
export type HousekeepingSlot = 'morning' | 'day' | 'evening' | 'dnd'

export type HousekeepingStatus = 'planned' | 'done' | 'skipped'

export interface HousekeepingTask {
  id: number
  date: string
  kind: HousekeepingKind
  slot: HousekeepingSlot
  status: HousekeepingStatus
  done_at: string | null
  // Гость меняет слот только запланированной ежедневной уборки на дату позже сегодняшней.
  can_change_slot: boolean
}

export interface AdminHousekeepingTask {
  id: number
  date: string
  kind: HousekeepingKind
  slot: HousekeepingSlot
  status: HousekeepingStatus
  done_at: string | null
  room: { slug: string, name: string }
  booking: { id: number, guest_name: string, phone: string }
  // Уборка после выезда, а в этот же номер сегодня заезжает другая бронь.
  arrival_today: boolean
}

export interface HousekeepingBoard {
  date: string
  checkout: AdminHousekeepingTask[]
  daily: Record<Exclude<HousekeepingSlot, 'dnd'>, AdminHousekeepingTask[]>
  dnd: AdminHousekeepingTask[]
  orders: AdminServiceOrder[]
}
