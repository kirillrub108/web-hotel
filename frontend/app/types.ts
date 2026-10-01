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
