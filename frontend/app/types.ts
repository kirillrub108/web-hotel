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
