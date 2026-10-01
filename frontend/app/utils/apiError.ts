interface ValidationIssue {
  loc?: unknown
  msg?: unknown
}

function errorDetail(error: unknown): unknown {
  return (error as { data?: { detail?: unknown } }).data?.detail
}

// Pydantic добавляет к тексту наших валидаторов префикс «Value error, ».
function cleanMessage(message: string): string {
  return message.replace(/^Value error, /, '')
}

// Текст ошибки API: строка detail или первое русское сообщение из ответа 422.
// Сообщения встроенных проверок Pydantic английские, вместо них показывается fallback.
export function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = errorDetail(error)
  if (typeof detail === 'string') {
    return detail
  }
  const first = Array.isArray(detail) ? (detail[0] as ValidationIssue) : undefined
  if (typeof first?.msg === 'string' && /[а-яё]/i.test(first.msg)) {
    return cleanMessage(first.msg)
  }
  return fallback
}

// Ошибки 422 по полям: { password: 'Слишком распространённый пароль' }. Только русские сообщения.
export function apiFieldErrors(error: unknown): Record<string, string> {
  const detail = errorDetail(error)
  const fields: Record<string, string> = {}
  if (!Array.isArray(detail)) {
    return fields
  }
  for (const issue of detail as ValidationIssue[]) {
    const field = Array.isArray(issue.loc) ? issue.loc.at(-1) : undefined
    if (typeof field === 'string' && typeof issue.msg === 'string' && /[а-яё]/i.test(issue.msg)) {
      fields[field] = cleanMessage(issue.msg)
    }
  }
  return fields
}
