// Сцены клиента. Каждая сцена отмечает шаги await d.step('ID') — ID совпадают со строками SCENARIO.md.
// state — сессия, сохранённая предыдущей сценой (work/state-*.json); saveState — сохранить сессию для следующих.
import { ACCOUNTS, hotelDate } from '../lib.mjs'

const nav = (d, name) => d.page.locator('#site-nav').getByRole('link', { name, exact: true })
const accountNav = (d, name) => d.page.getByRole('navigation', { name: 'Личный кабинет' }).getByRole('link', { name, exact: true })
const heading = (d, name) => d.page.getByRole('heading', { name, exact: true }).first()
const button = (d, name) => d.page.getByRole('button', { name, exact: true })
const roomCard = (d, name) => d.page.locator('.room', { has: d.page.getByRole('heading', { name, exact: true }) })

async function openRoom(d, name) {
  await d.click(nav(d, 'Номера'))
  await heading(d, 'Номера').waitFor()
  await d.page.locator('.room').first().waitFor()
  await d.hold(600)
  await d.click(roomCard(d, name).getByRole('link', { name: 'Подробнее' }))
  await heading(d, name).waitFor()
  await d.waitIdle()
}

async function login(d, account) {
  await heading(d, 'Вход').waitFor()
  await d.type(d.page.locator('#email'), account.email)
  await d.type(d.page.locator('#password'), account.password, { delay: 35 })
  await d.click(button(d, 'Войти'), { hold: 0 })
  await d.page.waitForURL(/\/account$/)
  await d.page.getByRole('heading', { name: /^Здравствуйте/ }).waitFor()
  await d.waitIdle()
}

// Заполнение формы брони: даты — по календарю гостиницы, стоимость считается сразу.
async function fillBooking(d, { phone, from, to, guests }) {
  const form = d.page.locator('.booking')
  await d.centerOn(form.getByRole('heading', { name: 'Бронирование' }))
  if (!(await d.page.locator('#guest_name').inputValue())) await d.type(d.page.locator('#guest_name'), ACCOUNTS.olga.name)
  await d.type(d.page.locator('#phone'), phone)
  await d.fill(d.page.locator('#check_in'), hotelDate(from))
  await d.fill(d.page.locator('#check_out'), hotelDate(to))
  await d.type(d.page.locator('#guests'), String(guests))
  await d.page.locator('.booking__total').waitFor()
  await d.moveTo(d.page.locator('.booking__total'))
}

export const scenes = {
  // Гость без входа: публичная часть сайта.
  K1: {
    async run(d) {
      await d.goto('/')
      await heading(d, 'Kivana').waitFor()
      await d.step('K1.1')
      await d.hold(1500)
      await d.scrollBy(650)
      await d.scrollBy(650)
      await d.scrollBy(650)
      await d.scrollTop()

      await d.step('K1.2')
      await d.click(nav(d, 'Номера'))
      await heading(d, 'Номера').waitFor()
      await d.page.locator('.room').first().waitFor()
      await d.hold(1500)

      await d.step('K1.3')
      await d.select(d.page.locator('#capacity'), { label: 'от 3' })
      await d.hold(1000)
      await d.select(d.page.locator('#max_price'), { label: 'до 10 000 ₽' })
      await d.hold(1500)
      await d.click(button(d, 'Сбросить'))
      await d.hold(1000)

      await d.step('K1.4')
      await d.click(roomCard(d, 'Люкс').getByRole('link', { name: 'Подробнее' }))
      await heading(d, 'Люкс').waitFor()
      await d.hold(1200)
      await d.moveTo(d.page.getByRole('heading', { name: 'Что в номере' }))
      await d.hold(1000)
      await d.moveTo(d.page.getByRole('link', { name: 'Войдите, чтобы забронировать' }))
      await d.hold(2000)

      await d.step('K1.5')
      await d.scrollTop(600)
      await d.click(nav(d, 'Услуги'))
      await heading(d, 'Услуги').waitFor()
      await d.hold(1200)
      await d.scrollBy(600)
      await d.hold(1200)

      await d.step('K1.6')
      await d.scrollTop(600)
      await d.click(nav(d, 'Контакты'))
      await heading(d, 'Контакты').waitFor()
      await d.hold(1200)
      await d.scrollBy(450)
      await d.hold(1500)
    },
  },

  // Регистрация новой гостьи, вход и подтверждение почты по ссылке из письма.
  K2: {
    saveState: 'olga',
    async run(d) {
      const olga = ACCOUNTS.olga
      await d.goto('/')
      await heading(d, 'Kivana').waitFor()

      await d.step('K2.1')
      await d.click(nav(d, 'Войти'))
      await heading(d, 'Вход').waitFor()
      await d.click(d.page.locator('.form-card__links').getByRole('link', { name: 'Зарегистрироваться' }))
      await heading(d, 'Регистрация').waitFor()
      await d.type(d.page.locator('#full_name'), olga.name)
      await d.type(d.page.locator('#email'), olga.email)
      await d.type(d.page.locator('#password'), olga.password)
      await d.moveTo(d.page.locator('.password__hint'))
      await d.hold(1500)
      await d.click(d.page.locator('label.checkbox input'))
      await d.click(button(d, 'Зарегистрироваться'), { hold: 0 })

      await d.step('K2.2')
      await heading(d, 'Проверьте почту').waitFor()
      await d.moveTo(d.page.locator('.form-card strong'))
      await d.hold(2500)

      await d.step('K2.3')
      await d.click(d.page.locator('.form-card').getByRole('link', { name: 'Войти' }))
      await login(d, olga)
      await d.hold(1200)

      await d.step('K2.4')
      await d.moveTo(d.page.locator('.banner strong'))
      await d.hold(1500)
      await d.click(button(d, 'Отправить письмо ещё раз'), { hold: 0 })
      // Письмо ушло при регистрации меньше минуты назад: приложение отвечает ограничением частоты.
      const resend = d.page.locator('.banner .notice')
      await resend.waitFor()
      await d.moveTo(resend)
      await d.hold(2200)
      await openRoom(d, 'Стандарт')
      await d.moveTo(d.page.getByRole('heading', { name: 'Подтвердите email' }))
      await d.hold(2500)

      await d.step('K2.5')
      const link = await d.mailLink(olga.email, 'verify-email')
      await d.banner('Открываем ссылку из письма', 1500)
      await d.goto(link)
      await heading(d, 'Подтверждение email').waitFor()
      await d.hold(800)
      await d.click(button(d, 'Подтвердить email'), { hold: 0 })
      await d.page.getByText('Email подтверждён. Спасибо!').waitFor()
      await d.hold(1800)
      await d.click(d.page.getByRole('link', { name: 'В личный кабинет' }), { hold: 0 })
      await d.page.getByRole('heading', { name: /^Здравствуйте/ }).waitFor()
      await d.waitIdle()
      await d.hold(1800)
    },
  },

  // Восстановление пароля по ссылке из письма, проверка политики паролей.
  K3: {
    async run(d) {
      const maria = ACCOUNTS.maria
      await d.goto('/')
      await heading(d, 'Kivana').waitFor()

      await d.step('K3.1')
      await d.click(nav(d, 'Войти'))
      await heading(d, 'Вход').waitFor()
      await d.click(d.page.getByRole('link', { name: 'Забыли пароль?' }))
      await heading(d, 'Восстановление пароля').waitFor()
      await d.type(d.page.locator('#email'), maria.email)
      await d.click(button(d, 'Отправить ссылку'), { hold: 0 })
      await heading(d, 'Проверьте почту').waitFor()
      await d.hold(2200)

      await d.step('K3.2')
      const link = await d.mailLink(maria.email, 'reset-password')
      await d.banner('Открываем ссылку из письма', 1500)
      await d.goto(link)
      await heading(d, 'Новый пароль').waitFor()
      await d.type(d.page.locator('#password'), 'qwerty123456789')
      await d.click(button(d, 'Сохранить пароль'), { hold: 0 })
      await d.page.locator('.field__error, .notice--error').first().waitFor()
      await d.moveTo(d.page.locator('.field__error, .notice--error').first())
      await d.hold(2500)

      await d.step('K3.3')
      await d.type(d.page.locator('#password'), maria.newPassword)
      await d.hold(600)
      await d.click(button(d, 'Сохранить пароль'), { hold: 0 })
      await heading(d, 'Пароль изменён').waitFor()
      await d.moveTo(d.page.locator('.notice--success'))
      await d.hold(2500)

      await d.step('K3.4')
      await d.click(d.page.locator('.form-card').getByRole('link', { name: 'Войти' }))
      await login(d, { email: maria.email, password: maria.newPassword })
      await d.hold(2200)
    },
  },

  // Бронь с промокодом: расчёт стоимости и автоматическое подтверждение.
  K4: {
    state: 'olga',
    saveState: 'olga',
    async run(d) {
      await d.goto('/account')
      await d.page.getByRole('heading', { name: /^Здравствуйте/ }).waitFor()

      await d.step('K4.1')
      await openRoom(d, 'Семейный')
      await d.moveTo(d.page.locator('.booking').getByRole('heading', { name: 'Бронирование' }))
      await d.hold(1800)

      await d.step('K4.2')
      await fillBooking(d, { phone: ACCOUNTS.olga.phone, from: 20, to: 23, guests: 3 })
      await d.hold(2200)

      await d.step('K4.3')
      await d.type(d.page.locator('#promo_code'), 'KIVANA-10')
      await d.click(d.page.locator('.booking__promo').getByRole('button', { name: 'Применить' }), { hold: 0 })
      await d.page.getByText(/^Скидка: −/).waitFor()
      await d.moveTo(d.page.locator('.booking__total'))
      await d.hold(2500)

      await d.step('K4.4')
      await d.click(d.page.locator('.booking__submit'), { hold: 0 })
      await heading(d, 'Заявка отправлена').waitFor()
      await d.moveTo(d.page.locator('.booking').getByText('Подтверждена', { exact: true }))
      await d.hold(2500)

      await d.step('K4.5')
      await d.click(d.page.getByRole('link', { name: 'Открыть бронь' }), { hold: 0 })
      await heading(d, 'История').waitFor()
      await d.waitIdle()
      await d.hold(1000)
      await d.moveTo(d.page.locator('.facts strong').first())
      await d.hold(1500)
      await d.moveTo(d.page.locator('.cancel__text'))
      await d.hold(1500)
      await d.moveTo(heading(d, 'История'))
      await d.hold(2000)
    },
  },

  // Спорная заявка: комментарий, большая сумма — ручная проверка администратором.
  K5: {
    state: 'olga',
    async run(d) {
      await d.goto('/account')
      await d.page.getByRole('heading', { name: /^Здравствуйте/ }).waitFor()

      await d.step('K5.1')
      await openRoom(d, 'Апартаменты')
      await fillBooking(d, { phone: ACCOUNTS.olga.phone, from: 45, to: 50, guests: 4 })
      await d.type(d.page.locator('#comment'), 'Приедем на машине, нужна парковка на все пять ночей.', { delay: 40 })
      await d.moveTo(d.page.locator('.booking__total'))
      await d.hold(1800)

      await d.step('K5.2')
      await d.click(d.page.locator('.booking__submit'), { hold: 0 })
      await heading(d, 'Заявка отправлена').waitFor()
      await d.moveTo(d.page.locator('.booking__reasons'))
      await d.hold(3500)

      await d.step('K5.3')
      await d.scrollTop(500)
      await d.click(nav(d, 'Кабинет'))
      await d.page.getByRole('heading', { name: /^Здравствуйте/ }).waitFor()
      await d.click(accountNav(d, 'Мои брони'))
      await heading(d, 'Мои брони').waitFor()
      await d.waitIdle()
      await d.moveTo(d.page.locator('.item').first())
      await d.hold(1500)
      await d.moveTo(d.page.locator('.item').nth(1))
      await d.hold(2000)
    },
  },

  // Проживающая гостья: кабинет, заказ услуги, отмена заказа, уборка, история.
  K6: {
    saveState: 'anna',
    async run(d) {
      const anna = ACCOUNTS.anna
      await d.goto('/')
      await heading(d, 'Kivana').waitFor()

      await d.step('K6.1')
      await d.click(nav(d, 'Войти'))
      await login(d, anna)
      await d.hold(1000)
      await d.moveTo(heading(d, 'Ближайшая бронь'))
      await d.hold(1500)
      await d.moveTo(heading(d, 'Персональные предложения'))
      await d.hold(800)
      await d.moveTo(d.page.locator('.overview', { has: heading(d, 'Персональные предложения') }).locator('p').first())
      await d.hold(2200)

      await d.step('K6.2')
      await d.scrollTop(500)
      await d.click(accountNav(d, 'Мои брони'))
      await heading(d, 'Мои брони').waitFor()
      await d.hold(1000)
      await d.click(d.page.locator('.item', { hasText: 'Студия' }).filter({ hasText: 'Проживание' }), { hold: 0 })
      await heading(d, 'Услуги и еда в номер').waitFor()
      await d.waitIdle()
      await d.hold(1200)
      await d.moveTo(heading(d, 'Услуги и еда в номер'))
      await d.hold(1500)

      await d.step('K6.3')
      const syrniki = await d.page.locator('#order-service option', { hasText: 'Сырники' }).textContent()
      await d.select(d.page.locator('#order-service'), { label: syrniki.trim() })
      await d.type(d.page.locator('#order-quantity'), '2')
      await d.fill(d.page.locator('#order-time'), `${hotelDate(1)}T09:30`)
      await d.type(d.page.locator('#order-comment'), 'Сметану отдельно, пожалуйста', { delay: 40 })
      await d.moveTo(d.page.locator('.order__total'))
      await d.hold(1200)
      await d.click(d.page.locator('form.order').getByRole('button', { name: 'Заказать' }), { hold: 0 })
      const newOrder = d.page.locator('.orders__item', { hasText: 'Сырники' })
      await newOrder.waitFor()
      await d.moveTo(newOrder)
      await d.hold(2200)

      await d.step('K6.4')
      const breakfast = d.page.locator('.orders__item', { hasText: 'Завтрак в номер' })
      await d.click(breakfast.getByRole('button', { name: 'Отменить' }), { hold: 0 })
      await breakfast.getByText('Отменён').waitFor()
      await d.moveTo(breakfast.getByText('Отменён'))
      await d.hold(2200)

      await d.step('K6.5')
      const slot = d.page.locator('.tasks select').first()
      await d.select(slot, { label: 'Не беспокоить' })
      await d.waitIdle()
      await d.hold(2200)

      await d.step('K6.6')
      await d.moveTo(heading(d, 'История'))
      await d.hold(1500)
      await d.moveTo(d.page.locator('.block').nth(1), { dy: 60 })
      await d.hold(2000)
    },
  },

  // Отмена будущей брони гостьей.
  K7: {
    state: 'anna',
    saveState: 'anna',
    async run(d) {
      await d.goto('/account/bookings')
      await heading(d, 'Мои брони').waitFor()

      await d.step('K7.1')
      await d.hold(800)
      await d.click(d.page.locator('.item', { hasText: 'Стандарт' }).filter({ hasText: 'Подтверждена' }), { hold: 0 })
      await heading(d, 'История').waitFor()
      await d.waitIdle()
      await d.moveTo(d.page.locator('.cancel__text'))
      await d.hold(1800)
      await d.click(button(d, 'Отменить бронь'))
      await d.page.locator('.cancel__confirm').waitFor()
      await d.hold(1500)
      await d.click(button(d, 'Да, отменить'), { hold: 0 })

      await d.step('K7.2')
      const badge = d.page.locator('.block__head').getByText('Отменена', { exact: true })
      await badge.waitFor()
      await d.moveTo(badge)
      await d.hold(1800)
      await d.moveTo(heading(d, 'История'), { dy: 80 })
      await d.hold(2000)
      // Промокод ANNA-10 был занят этой бронью — после отмены он снова в персональных предложениях.
      await d.scrollTop(500)
      await d.click(accountNav(d, 'Обзор'), { hold: 0 })
      const offer = d.page.locator('.offer', { hasText: 'ANNA-10' })
      await offer.waitFor()
      await d.moveTo(offer)
      await d.hold(2500)
    },
  },

  // Профиль, смена пароля, закрытый раздел администратора и выход.
  K8: {
    state: 'anna',
    async run(d) {
      const anna = ACCOUNTS.anna
      await d.goto('/account')
      await d.page.getByRole('heading', { name: /^Здравствуйте/ }).waitFor()

      await d.step('K8.1')
      await d.click(accountNav(d, 'Профиль'))
      await heading(d, 'Профиль').waitFor()
      await d.waitIdle()
      await d.type(d.page.locator('#phone'), '+7 900 111-22-99')
      await d.click(d.page.locator('form', { has: heading(d, 'Профиль') }).getByRole('button', { name: 'Сохранить' }), { hold: 0 })
      await d.page.getByText('Профиль сохранён.').waitFor()
      await d.moveTo(d.page.getByText('Профиль сохранён.'))
      await d.hold(1800)

      await d.step('K8.2')
      await d.type(d.page.locator('#current_password'), anna.password, { delay: 35 })
      await d.type(d.page.locator('#new_password'), anna.newPassword, { delay: 35 })
      await d.click(button(d, 'Сменить пароль'), { hold: 0 })
      await d.page.getByText(/Пароль изменён/).waitFor()
      await d.moveTo(d.page.getByText(/Пароль изменён/))
      await d.hold(2200)

      await d.step('K8.3')
      await d.banner('Переход по адресу localhost:3000/admin', 1500)
      await d.goto('/admin')
      await d.page.waitForURL(/\/account$/)
      await d.page.getByRole('heading', { name: /^Здравствуйте/ }).waitFor()
      await d.hold(2500)

      await d.step('K8.4')
      await d.click(accountNav(d, 'Профиль'))
      await heading(d, 'Профиль').waitFor()
      await d.click(button(d, 'Выйти из аккаунта'), { hold: 0 })
      await nav(d, 'Войти').waitFor()
      await d.scrollTop(300)
      await d.moveTo(nav(d, 'Войти'))
      await d.hold(2500)
    },
  },
}
