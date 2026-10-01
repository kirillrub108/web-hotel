import type { AdminPromo, Promo, PromoForm } from '~/types'

// Размер скидки: «−10%» или «−1 500 ₽».
export function promoValueLabel(promo: Pick<Promo, 'kind' | 'value'>): string {
  return promo.kind === 'percent' ? `−${promo.value}%` : `−${formatRubles(promo.value)}`
}

// Условия акции списком фраз: срок, минимум ночей, номер. Потолок процента соответствует PROMO_MAX_PERCENT backend.
export function promoConditions(promo: Promo): string[] {
  const conditions = [`Действует с ${formatDate(promo.valid_from)} по ${formatDate(promo.valid_to)}`]
  if (promo.min_nights > 1) {
    conditions.push(`Минимум ночей: ${promo.min_nights}`)
  }
  if (promo.room) {
    conditions.push(`Только для номера «${promo.room.name}»`)
  }
  if (promo.kind === 'percent') {
    conditions.push('Скидка не больше 50% от стоимости проживания')
  }
  conditions.push('Код одноразовый')
  return conditions
}

// Полное тело изменения акции: PATCH принимает все поля сразу.
export function promoToForm(promo: AdminPromo): PromoForm {
  return {
    code: promo.code,
    title: promo.title,
    description: promo.description,
    kind: promo.kind,
    value: promo.value,
    valid_from: promo.valid_from,
    valid_to: promo.valid_to,
    min_nights: promo.min_nights,
    room_id: promo.room_id,
    user_id: promo.user?.id ?? null,
    is_active: promo.is_active,
  }
}

// Деактивация и повторное включение. Брони, уже применившие акцию, не меняются.
export async function setPromoActive(promo: AdminPromo, isActive: boolean): Promise<void> {
  await $fetch(`/api/admin/promos/${promo.id}`, {
    method: 'PATCH',
    body: { ...promoToForm(promo), is_active: isActive },
  })
}

// Состояние акции для таблицы админки.
export function promoStateLabel(promo: AdminPromo, today: string): string {
  if (!promo.is_active) {
    return 'Отключена'
  }
  if (promo.valid_to < today) {
    return 'Срок истёк'
  }
  if (promo.valid_from > today) {
    return 'Ещё не началась'
  }
  return promo.in_use ? 'Код занят бронью' : 'Действует'
}
