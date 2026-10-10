// Сцены администратора. Сессия администратора создаётся в A1 и переиспользуется в A2–A8.
import { ACCOUNTS, hotelDate } from '../lib.mjs'

const heading = (d, name) => d.page.getByRole('heading', { name, exact: true }).first()
const button = (d, name) => d.page.getByRole('button', { name, exact: true })
const adminNav = (d, name) => d.page.getByRole('navigation', { name: 'Разделы админки' }).getByRole('link', { name, exact: true })
const tab = (d, name) => d.page.getByRole('tab', { name, exact: true })
const row = (d, ...texts) => texts.reduce((loc, text) => loc.filter({ hasText: text }), d.page.locator('tbody tr'))
const dialog = (d) => d.page.locator('dialog[open]')

async function openSection(d, name) {
  await d.click(adminNav(d, name), { hold: 0 })
  await heading(d, name).waitFor()
  await d.waitIdle()
}

// Модальное окно: ввод причины/комментария и отправка; ждём, пока окно закроется.
async function submitDialog(d) {
  await d.click(dialog(d).locator('button[type=submit]'), { hold: 0 })
  await dialog(d).waitFor({ state: 'detached' })
  await d.waitIdle()
}

async function typeNumber(d, locator, value) {
  await d.type(locator, String(value))
}

export const scenes = {
  // Вход администратора и защита закрытого раздела.
  A1: {
    saveState: 'admin',
    async run(d) {
      await d.goto('/')
      await heading(d, 'Kivana').waitFor()
      await d.step('A1.1')
      await d.hold(800)
      await d.banner('Переход по адресу localhost:3000/admin без входа', 1600)
      await d.goto('/admin')
      await d.page.waitForURL(/\/login\?next=/)
      await heading(d, 'Вход').waitFor()
      await d.hold(1800)

      await d.step('A1.2')
      await d.type(d.page.locator('#email'), ACCOUNTS.admin.email)
      await d.type(d.page.locator('#password'), ACCOUNTS.admin.password, { delay: 35 })
      await d.click(button(d, 'Войти'), { hold: 0 })
      await d.page.waitForURL(/\/admin$/)
      await heading(d, 'Заявки').waitFor()
      await d.waitIdle()
      await d.hold(2200)
    },
  },

  // Заявки: разбор, история, подтверждение, отклонение, фильтры, пагинация, отмена брони.
  A2: {
    state: 'admin',
    async run(d) {
      await d.goto('/admin')
      await heading(d, 'Заявки').waitFor()

      await d.step('A2.1')
      await d.click(tab(d, 'На разборе'))
      const olga = row(d, 'Ольга Смирнова', 'Апартаменты')
      await olga.waitFor()
      await d.moveTo(olga.locator('.reasons'))
      await d.hold(2500)
      await d.moveTo(olga.locator('.comment'))
      await d.hold(1500)

      await d.step('A2.2')
      await d.click(olga.getByRole('button', { name: 'История' }), { hold: 0 })
      await d.page.locator('tr.history').waitFor()
      await d.moveTo(d.page.locator('tr.history'))
      await d.hold(2500)
      await d.click(olga.getByRole('button', { name: 'Скрыть историю' }))

      await d.step('A2.3')
      await d.click(olga.getByRole('button', { name: 'Подтвердить' }), { hold: 0 })
      await dialog(d).waitFor()
      await d.hold(800)
      await d.type(d.page.locator('#admin-reason'), 'Парковка забронирована, ждём вас!', { delay: 40 })
      await d.hold(600)
      await submitDialog(d)
      await olga.waitFor({ state: 'detached' })
      await d.hold(1500)

      await d.step('A2.4')
      const maria = row(d, 'Мария Орлова')
      await d.click(maria.getByRole('button', { name: 'Отклонить' }), { hold: 0 })
      await dialog(d).waitFor()
      await d.hold(600)
      await d.type(d.page.locator('#admin-reason'), 'На эти даты номер закрыт на ремонт.', { delay: 40 })
      await d.hold(600)
      await submitDialog(d)
      await d.page.getByText('Заявок с таким статусом пока нет.').waitFor()
      await d.hold(1800)

      await d.step('A2.5')
      await d.click(tab(d, 'Подтверждённые'), { hold: 0 })
      await row(d, 'Ольга Смирнова', 'Апартаменты').waitFor()
      await d.moveTo(row(d, 'Ольга Смирнова', 'Апартаменты'))
      await d.hold(1800)
      await d.click(tab(d, 'Отклонённые'), { hold: 0 })
      await row(d, 'Мария Орлова').waitFor()
      await d.hold(1800)
      await d.click(tab(d, 'Отменённые'), { hold: 0 })
      await row(d, 'Анна Лебедева').waitFor()
      await d.moveTo(row(d, 'Анна Лебедева'))
      await d.hold(1800)

      await d.step('A2.6')
      await d.click(tab(d, 'Все'), { hold: 0 })
      await d.page.locator('.pager').waitFor()
      await d.waitIdle()
      await d.hold(800)
      await d.click(d.page.locator('.pager').getByRole('button', { name: 'Вперёд' }), { hold: 0 })
      await d.page.locator('.pager').getByText(/^21–/).waitFor()
      await d.hold(1800)
      await d.click(d.page.locator('.pager').getByRole('button', { name: 'Назад' }), { hold: 0 })
      await d.page.locator('.pager').getByText(/^1–20/).waitFor()
      await d.hold(1000)

      await d.step('A2.7')
      await d.scrollTop(600)
      await d.click(tab(d, 'Подтверждённые'), { hold: 0 })
      await d.page.locator('[role=tab][aria-selected=true]', { hasText: 'Подтверждённые' }).waitFor()
      await d.waitIdle()
      const family = row(d, 'Ольга Смирнова', 'Семейный')
      await family.waitFor()
      await d.hold(800)
      await d.click(family.getByRole('button', { name: 'Отменить' }), { hold: 0 })
      await dialog(d).waitFor()
      await d.hold(600)
      await d.type(d.page.locator('#admin-reason'), 'Гостья попросила отменить бронь по телефону.', { delay: 40 })
      await submitDialog(d)
      await family.waitFor({ state: 'detached' })
      await d.click(tab(d, 'Отменённые'), { hold: 0 })
      await row(d, 'Ольга Смирнова', 'Семейный').waitFor()
      await d.moveTo(row(d, 'Ольга Смирнова', 'Семейный'))
      await d.hold(2200)
    },
  },

  // CRM: список, поиск, карточка клиента, статус и заметка, персональная акция.
  A3: {
    state: 'admin',
    async run(d) {
      await d.goto('/admin')
      await heading(d, 'Заявки').waitFor()

      await d.step('A3.1')
      await openSection(d, 'Клиенты')
      await d.hold(1500)
      await d.click(d.page.locator('.pager').getByRole('button', { name: 'Вперёд' }), { hold: 0 })
      await d.page.locator('.pager').getByText(/^21–/).waitFor()
      await d.hold(1500)
      await d.click(d.page.locator('.pager').getByRole('button', { name: 'Назад' }), { hold: 0 })
      await d.page.locator('.pager').getByText(/^1–20/).waitFor()
      await d.scrollTop(600)

      await d.step('A3.2')
      await d.type(d.page.locator('#client-search'), 'Ольга')
      await d.click(d.page.locator('form.search').getByRole('button', { name: 'Найти' }), { hold: 0 })
      await row(d, 'Ольга Виноградова').waitFor()
      await d.waitIdle()
      await d.hold(2200)

      await d.step('A3.3')
      await d.click(d.page.getByRole('link', { name: 'Ольга Смирнова' }), { hold: 0 })
      await heading(d, 'Статус и заметка').waitFor()
      await d.waitIdle()
      await d.moveTo(heading(d, 'Профиль и показатели'))
      await d.hold(1500)
      await d.moveTo(heading(d, 'Брони клиента'))
      await d.hold(2000)
      await d.scrollTop(600)

      await d.step('A3.4')
      await d.select(d.page.locator('#crm-status'), { label: 'VIP' })
      await d.type(d.page.locator('#crm-note'), 'Путешествует на машине, всегда нужна парковка.', { delay: 40 })
      await d.click(d.page.locator('form', { has: heading(d, 'Статус и заметка') }).getByRole('button', { name: 'Сохранить' }), { hold: 0 })
      await d.page.getByText('Сохранено.').waitFor()
      await d.moveTo(d.page.getByText('Сохранено.'))
      await d.hold(1800)

      await d.step('A3.5')
      await d.click(button(d, 'Выдать персональную акцию'), { hold: 0 })
      await dialog(d).waitFor()
      await d.hold(600)
      await d.type(d.page.locator('#promo-code'), 'OLGA-15')
      await d.type(d.page.locator('#promo-title'), 'Скидка 15% для Ольги', { delay: 40 })
      await d.type(d.page.locator('#promo-description'), 'Спасибо, что выбрали Kivana.', { delay: 40 })
      await d.select(d.page.locator('#promo-kind'), { label: 'Процент' })
      await typeNumber(d, d.page.locator('#promo-value'), 15)
      await d.fill(d.page.locator('#promo-from'), hotelDate(0))
      await d.fill(d.page.locator('#promo-to'), hotelDate(90))
      await typeNumber(d, d.page.locator('#promo-nights'), 2)
      await d.hold(800)
      await submitDialog(d)
      const promo = row(d, 'OLGA-15')
      await promo.waitFor()
      await d.moveTo(promo)
      await d.hold(2000)

      await d.step('A3.6')
      await d.click(promo.getByRole('button', { name: 'Деактивировать' }), { hold: 0 })
      await promo.getByRole('button', { name: 'Включить' }).waitFor()
      await d.hold(1600)
      await d.click(promo.getByRole('button', { name: 'Включить' }), { hold: 0 })
      await promo.getByRole('button', { name: 'Деактивировать' }).waitFor()
      await d.hold(1600)
    },
  },

  // Номера: цена, описание, снятие с продажи и проверка на сайте.
  A4: {
    state: 'admin',
    async run(d) {
      await d.goto('/admin')
      await heading(d, 'Заявки').waitFor()
      const econom = row(d, 'Эконом')

      await d.step('A4.1')
      await openSection(d, 'Номера')
      await d.moveTo(econom)
      await d.hold(2000)

      await d.step('A4.2')
      await d.click(econom.getByRole('button', { name: 'Изменить' }), { hold: 0 })
      await dialog(d).waitFor()
      await d.hold(600)
      await typeNumber(d, d.page.locator('#room-price'), 3100)
      await d.click(d.page.locator('#room-description'), { hold: 100 })
      await d.page.keyboard.press('Control+End')
      await d.page.locator('#room-description').pressSequentially(' После ремонта 2026 года.', { delay: 40 })
      await d.hold(800)
      await submitDialog(d)
      await econom.getByText('3 100').waitFor()
      await d.moveTo(econom.getByText('3 100'))
      await d.hold(1800)

      await d.step('A4.3')
      await d.click(econom.getByRole('button', { name: 'Изменить' }), { hold: 0 })
      await dialog(d).waitFor()
      await d.hold(500)
      await d.click(dialog(d).locator('label.checkbox input'))
      await d.moveTo(dialog(d).locator('.dialog__hint').last())
      await d.hold(1200)
      await submitDialog(d)
      await econom.getByText('Снят с продажи').waitFor()
      await d.moveTo(econom.getByText('Снят с продажи'))
      await d.hold(1800)

      await d.step('A4.4')
      await d.banner('Открываем карточку номера на сайте: localhost:3000/rooms/econom', 1600)
      await d.goto('/rooms/econom')
      await heading(d, 'Эконом').waitFor()
      await d.moveTo(d.page.getByRole('heading', { name: 'Номер недоступен' }))
      await d.hold(2800)

      await d.step('A4.5')
      await d.goto('/admin/rooms')
      await heading(d, 'Номера').waitFor()
      await d.click(econom.getByRole('button', { name: 'Изменить' }), { hold: 0 })
      await dialog(d).waitFor()
      await d.hold(400)
      await d.click(dialog(d).locator('label.checkbox input'))
      await d.hold(600)
      await submitDialog(d)
      await econom.getByText('Доступен').waitFor()
      await d.moveTo(econom.getByText('Доступен'))
      await d.hold(2000)
    },
  },

  // Акции: вкладки, создание, редактирование, деактивация, удаление.
  A5: {
    state: 'admin',
    async run(d) {
      await d.goto('/admin')
      await heading(d, 'Заявки').waitFor()

      await d.step('A5.1')
      await openSection(d, 'Акции')
      await d.hold(1200)
      await d.click(tab(d, 'Общие'), { hold: 1500 })
      await d.click(tab(d, 'Персональные'), { hold: 1500 })
      await d.click(tab(d, 'Все'), { hold: 1200 })

      await d.step('A5.2')
      await d.click(button(d, 'Новая акция'), { hold: 0 })
      await dialog(d).waitFor()
      await d.hold(500)
      await d.type(d.page.locator('#promo-code'), 'AUTUMN-15')
      await d.type(d.page.locator('#promo-title'), 'Осенняя скидка 15%', { delay: 40 })
      await d.type(d.page.locator('#promo-description'), 'Для всех гостей при проживании от двух ночей.', { delay: 35 })
      await typeNumber(d, d.page.locator('#promo-value'), 15)
      await d.fill(d.page.locator('#promo-from'), hotelDate(0))
      await d.fill(d.page.locator('#promo-to'), hotelDate(60))
      await typeNumber(d, d.page.locator('#promo-nights'), 2)
      await d.hold(800)
      await submitDialog(d)
      const autumn = row(d, 'AUTUMN-15')
      await autumn.waitFor()
      await d.moveTo(autumn)
      await d.hold(2000)

      await d.step('A5.3')
      await d.click(autumn.getByRole('button', { name: 'Изменить' }), { hold: 0 })
      await dialog(d).waitFor()
      await d.hold(500)
      await d.type(d.page.locator('#promo-title'), 'Осенняя скидка 20%', { delay: 40 })
      await typeNumber(d, d.page.locator('#promo-value'), 20)
      await d.hold(600)
      await submitDialog(d)
      await autumn.getByText('Осенняя скидка 20%').waitFor()
      await d.moveTo(autumn.getByText('Осенняя скидка 20%'))
      await d.hold(1800)

      await d.step('A5.4')
      await d.click(autumn.getByRole('button', { name: 'Деактивировать' }), { hold: 0 })
      await autumn.getByRole('button', { name: 'Включить' }).waitFor()
      await d.moveTo(autumn.locator('td[data-label="Состояние"]'))
      await d.hold(1600)
      await d.click(autumn.getByRole('button', { name: 'Включить' }), { hold: 0 })
      await autumn.getByRole('button', { name: 'Деактивировать' }).waitFor()
      await d.hold(1400)

      await d.step('A5.5')
      await d.clickConfirm(autumn.getByRole('button', { name: 'Удалить' }))
      await autumn.waitFor({ state: 'detached' })
      await d.hold(1600)
    },
  },

  // Услуги: создание, цена, отключение, удаление.
  A6: {
    state: 'admin',
    async run(d) {
      await d.goto('/admin')
      await heading(d, 'Заявки').waitFor()

      await d.step('A6.1')
      await openSection(d, 'Услуги')
      await d.hold(1500)
      await d.scrollBy(500)
      await d.hold(1000)
      await d.scrollTop(600)

      await d.step('A6.2')
      await d.click(button(d, 'Новая услуга'), { hold: 0 })
      await dialog(d).waitFor()
      await d.hold(500)
      await d.type(d.page.locator('#service-title'), 'Прокат велосипеда', { delay: 40 })
      await d.type(d.page.locator('#service-slug'), 'prokat-velosipeda', { delay: 35 })
      await d.type(d.page.locator('#service-description'), 'Городской велосипед на день, шлем и замок в комплекте.', { delay: 30 })
      await d.select(d.page.locator('#service-category'), { label: 'Другое' })
      await d.select(d.page.locator('#service-unit'), { label: 'за штуку' })
      await typeNumber(d, d.page.locator('#service-price'), 1200)
      await typeNumber(d, d.page.locator('#service-sort'), 5)
      await d.hold(800)
      await submitDialog(d)
      const bike = row(d, 'Прокат велосипеда')
      await bike.waitFor()
      await d.moveTo(bike)
      await d.hold(2000)

      await d.step('A6.3')
      await d.click(bike.getByRole('button', { name: 'Изменить' }), { hold: 0 })
      await dialog(d).waitFor()
      await d.hold(500)
      await typeNumber(d, d.page.locator('#service-price'), 900)
      await d.hold(600)
      await submitDialog(d)
      await bike.getByText(/900/).waitFor()
      await d.moveTo(bike.getByText(/900/))
      await d.hold(1800)

      await d.step('A6.4')
      await d.click(bike.getByRole('button', { name: 'Деактивировать' }), { hold: 0 })
      await bike.getByText('Отключена').waitFor()
      await d.moveTo(bike.getByText('Отключена'))
      await d.hold(2000)

      await d.step('A6.5')
      await d.clickConfirm(bike.getByRole('button', { name: 'Удалить' }))
      await bike.waitFor({ state: 'detached' })
      await d.hold(1600)
    },
  },

  // Заказы услуг: фильтры и обработка заказа гостьи из сцены K6.
  A7: {
    state: 'admin',
    async run(d) {
      await d.goto('/admin')
      await heading(d, 'Заявки').waitFor()

      await d.step('A7.1')
      await openSection(d, 'Заказы услуг')
      await d.hold(1500)
      await d.select(d.page.locator('#orders-status'), { label: 'Новый' })
      await d.waitIdle()
      await row(d, 'Сырники').waitFor()
      await d.moveTo(row(d, 'Сырники'))
      await d.hold(2000)

      await d.step('A7.2')
      await d.select(d.page.locator('#orders-status'), { label: 'Все' })
      await d.waitIdle()
      await d.fill(d.page.locator('#orders-date'), hotelDate(1))
      await d.waitIdle()
      await d.hold(2000)
      await d.click(button(d, 'Сбросить дату'), { hold: 0 })
      await d.waitIdle()
      await d.hold(1200)

      await d.step('A7.3')
      const order = row(d, 'Сырники')
      await d.click(order.getByRole('button', { name: 'Принять' }), { hold: 0 })
      await order.getByText('Принят', { exact: true }).waitFor()
      await d.moveTo(order.getByText('Принят', { exact: true }))
      await d.hold(1600)
      await d.click(order.getByRole('button', { name: 'Выполнен' }), { hold: 0 })
      await order.getByText('Выполнен', { exact: true }).waitFor()
      await d.moveTo(order.getByText('Выполнен', { exact: true }))
      await d.hold(2000)
    },
  },

  // Уборка: доска на день, отметки, другая дата, выход.
  A8: {
    state: 'admin',
    async run(d) {
      await d.goto('/admin')
      await heading(d, 'Заявки').waitFor()

      await d.step('A8.1')
      await openSection(d, 'Уборка')
      await d.hold(1500)
      await d.moveTo(heading(d, 'Ежедневные уборки'))
      await d.hold(1500)
      await d.moveTo(heading(d, 'Не беспокоить'))
      await d.hold(1200)
      await d.scrollTop(600)

      await d.step('A8.2')
      const task = d.page.locator('li.row', { hasText: 'Студия' }).first()
      await d.click(task.getByRole('button', { name: 'Пропущено' }), { hold: 0 })
      await task.getByText('Пропущена', { exact: true }).waitFor()
      await d.hold(1500)
      await d.click(task.getByRole('button', { name: 'Выполнено' }), { hold: 0 })
      await task.getByText('Выполнена', { exact: true }).waitFor()
      await d.hold(1500)

      await d.step('A8.3')
      await d.fill(d.page.locator('#board-date'), hotelDate(1))
      await d.waitIdle()
      // Список «Не беспокоить» идёт сразу за своим заголовком; в нём — выбор Анны из сцены K6.
      const dndRow = d.page.locator('h2:text-is("Не беспокоить") ~ ul.list li.row', { hasText: 'Анна Лебедева' })
      await dndRow.waitFor()
      await d.moveTo(heading(d, 'Не беспокоить'))
      await d.hold(600)
      await d.moveTo(dndRow)
      await d.hold(2500)
      await d.scrollTop(500)
      await d.click(button(d, 'Сегодня'), { hold: 1200 })

      await d.step('A8.4')
      await d.click(adminNav(d, 'Заявки'), { hold: 0 })
      await heading(d, 'Заявки').waitFor()
      await d.hold(800)
      await d.click(button(d, 'Выйти'), { hold: 0 })
      await d.page.waitForURL(/\/login/)
      await heading(d, 'Вход').waitFor()
      await d.hold(2200)
    },
  },
}
