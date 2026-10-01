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

export type BookingStatus = 'new' | 'confirmed' | 'cancelled'

export interface AdminBooking {
  id: number
  room_id: number
  guest_name: string
  phone: string
  email: string
  check_in: string
  check_out: string
  guests: number
  comment: string | null
  status: BookingStatus
  created_at: string
  room: { slug: string, name: string }
}

export interface AdminBookingPage {
  items: AdminBooking[]
  total: number
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
