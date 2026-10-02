// Помощники записи: видимый курсор, плавные движения мыши, посимвольный ввод, метки шагов для субтитров.
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const DEMO_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
export const WORK_DIR = path.join(DEMO_DIR, 'work')
export const RAW_DIR = path.join(DEMO_DIR, 'raw')
export const BASE_URL = process.env.APP_URL || 'http://localhost:3000'
export const VIEWPORT = { width: 1920, height: 1080 }

export const ACCOUNTS = {
  admin: { email: 'admin@kivana.ru', password: 'tidy copper lantern orbit' },
  anna: { email: 'anna@demo.kivana.ru', password: 'silver harbor morning tea', newPassword: 'copper kettle winter sun' },
  maria: { email: 'maria@demo.kivana.ru', password: 'silver harbor morning tea', newPassword: 'quiet garden amber lamp' },
  olga: { name: 'Ольга Смирнова', email: 'olga.smirnova@example.com', password: 'lilac river evening walk', phone: '+7 916 555-12-34' },
}

// Даты считаются по часовому поясу гостиницы, как и в сиде: «сегодня» у backend и у сценария совпадает.
export function hotelDate(offsetDays = 0) {
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Moscow' }).format(new Date())
  const d = new Date(`${today}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + offsetDays)
  return d.toISOString().slice(0, 10)
}

// Курсор и кольцо клика. Слой — manual popover: он в top layer, поэтому виден и поверх модальных <dialog>
// (при открытии диалога слой поднимается заново, чтобы оказаться выше него).
const CURSOR_SCRIPT = `(() => {
  if (window.top !== window) return;
  const install = () => {
    if (document.getElementById('__demo_layer')) return;
    const style = document.createElement('style');
    style.textContent = \`
      #__demo_layer{position:fixed;inset:0;width:100vw;height:100vh;margin:0;padding:0;border:0;background:transparent;
        overflow:visible;pointer-events:none;z-index:2147483647}
      #__demo_cursor{position:absolute;left:0;top:0;width:28px;height:28px;margin:-3px 0 0 -4px;pointer-events:none;
        filter:drop-shadow(0 2px 3px rgba(0,0,0,.45));transition:transform .08s linear}
      .__demo_ring{position:absolute;width:56px;height:56px;margin:-28px 0 0 -28px;border-radius:50%;pointer-events:none;
        border:4px solid rgba(255,90,40,.95);background:rgba(255,120,60,.25);animation:__demo_pulse .65s ease-out forwards}
      @keyframes __demo_pulse{from{transform:scale(.3);opacity:1}to{transform:scale(1.5);opacity:0}}
      #__demo_sync{position:absolute;left:4px;bottom:4px;width:12px;height:12px;display:none}
      #__demo_banner{position:absolute;left:50%;top:96px;transform:translateX(-50%);max-width:1100px;padding:18px 28px;
        background:#1f2937;color:#fff;font:500 24px/1.4 system-ui,sans-serif;border-radius:14px;
        box-shadow:0 12px 32px rgba(0,0,0,.35);border-left:8px solid #ff5a28}\`;
    document.documentElement.appendChild(style);
    const layer = document.createElement('div');
    layer.id = '__demo_layer';
    layer.setAttribute('popover', 'manual');
    layer.innerHTML = '<svg id="__demo_cursor" viewBox="0 0 24 24"><path d="M3 2l16 9.5-7 1.6-3.6 6.4z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.body.appendChild(layer);
    // Метка шага: квадрат в углу меняет цвет на каждом шаге; build.mjs берёт по ней время субтитров прямо из видео.
    const sync = document.createElement('div');
    sync.id = '__demo_sync';
    layer.appendChild(sync);
    window.__demoSync = (n) => {
      try { sessionStorage.setItem('__demoStep', String(n)); } catch (e) {}
      sync.style.display = n > 0 ? 'block' : 'none';
      sync.style.background = n % 2 ? '#ff0000' : '#0000ff';
    };
    let step = 0;
    try { step = Number(sessionStorage.getItem('__demoStep') || 0); } catch (e) {}
    window.__demoSync(step);
    const raise = () => { try { if (layer.matches(':popover-open')) layer.hidePopover(); layer.showPopover(); } catch (e) {} };
    raise();
    const cursor = layer.querySelector('#__demo_cursor');
    const pos = window.__demoPos || { x: 960, y: 540 };
    const place = (x, y) => { pos.x = x; pos.y = y; window.__demoPos = pos; cursor.style.transform = 'translate(' + x + 'px,' + y + 'px)'; };
    place(pos.x, pos.y);
    window.addEventListener('mousemove', e => place(e.clientX, e.clientY), true);
    window.__demoRing = (x, y) => {
      const ring = document.createElement('div');
      ring.className = '__demo_ring';
      ring.style.left = x + 'px'; ring.style.top = y + 'px';
      layer.appendChild(ring);
      setTimeout(() => ring.remove(), 700);
    };
    window.addEventListener('mousedown', e => window.__demoRing(e.clientX, e.clientY), true);
    window.__demoBanner = (text) => {
      let b = document.getElementById('__demo_banner');
      if (!text) { if (b) b.remove(); return; }
      if (!b) { b = document.createElement('div'); b.id = '__demo_banner'; layer.appendChild(b); }
      b.textContent = text;
      raise();
    };
    new MutationObserver(muts => {
      if (muts.some(m => m.target.tagName === 'DIALOG' && m.attributeName === 'open')) raise();
    }).observe(document.body, { attributes: true, subtree: true, attributeFilter: ['open'] });
  };
  if (document.body) install(); else document.addEventListener('DOMContentLoaded', install);
})();`

export class Demo {
  constructor(page, sceneId) {
    this.page = page
    this.sceneId = sceneId
    this.t0 = Date.now()
    this.marks = []
    this.mouse = { x: 960, y: 540 }
    this.lastDialog = null
    page.on('dialog', async (dialog) => {
      this.lastDialog = dialog.message()
      await dialog.accept()
    })
  }

  static async install(context) {
    await context.addInitScript(CURSOR_SCRIPT)
  }

  now() { return (Date.now() - this.t0) / 1000 }

  // Метка синхронизации: страница меняет цвет с пурпурного на зелёный; build.mjs находит этот кадр в видео
  // и по нему сдвигает метки шагов (запись видео начинается не в тот же миг, что и отсчёт сцены).
  async syncFlash() {
    await this.page.setContent('<html><body style="margin:0;height:100vh;background:#ff00ff"></body></html>')
    await this.page.waitForTimeout(700)
    const at = await this.page.evaluate(() => new Promise((resolve) => {
      setTimeout(() => {
        document.body.style.background = '#00ff00'
        requestAnimationFrame(() => resolve(Date.now()))
      }, 50)
    }))
    await this.page.waitForTimeout(500)
    return (at - this.t0) / 1000
  }

  // Начало шага: с этого момента показывается субтитр строки SCENARIO.md с тем же ID.
  // Метка ставится и в кадре (квадрат меняет цвет): по ней build.mjs синхронизирует субтитры с видео.
  async step(id) {
    this.marks.push({ id, t: this.now() })
    console.log(`  · ${id} @ ${this.now().toFixed(1)}s`)
    await this.page.evaluate((n) => window.__demoSync?.(n), this.marks.length)
  }

  // Конец сцены: последняя смена цвета метки — граница обрезки.
  async endMark() {
    await this.page.evaluate((n) => window.__demoSync?.(n), this.marks.length + 1)
    await this.page.waitForTimeout(400)
    return this.now()
  }

  async hold(ms = 1500) { await this.page.waitForTimeout(ms) }

  async goto(urlPath) {
    await this.page.goto(new URL(urlPath, BASE_URL).toString(), { waitUntil: 'domcontentloaded' })
    await this.page.waitForLoadState('networkidle').catch(() => {})
    await this.syncMouse()
  }

  // После перехода init-скрипт рисует курсор в сохранённой позиции; возвращаем туда же и реальную мышь.
  async syncMouse() {
    await this.page.evaluate(({ x, y }) => { window.__demoPos = { x, y } }, this.mouse).catch(() => {})
    await this.page.mouse.move(this.mouse.x, this.mouse.y)
  }

  async waitIdle() { await this.page.waitForLoadState('networkidle').catch(() => {}) }

  async centerOn(locator) {
    await locator.waitFor({ state: 'visible' })
    const moved = await locator.evaluate((el) => {
      const r = el.getBoundingClientRect()
      const margin = 160 // нижняя полоса кадра занята субтитрами
      const x = r.left + Math.min(r.width / 2, 120)
      const y = r.top + r.height / 2
      // Элемент должен быть в кадре и не обрезан прокручиваемым контейнером (например, широкой таблицей).
      const hit = x >= 0 && x <= window.innerWidth && y >= 0 && y <= window.innerHeight ? document.elementFromPoint(x, y) : null
      const reachable = hit && (hit === el || el.contains(hit))
      if (reachable && r.top >= 90 && r.bottom <= window.innerHeight - margin) return false
      el.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' })
      return true
    })
    if (moved) await this.settle(locator)
  }

  // Ждём окончания плавной прокрутки: позиция элемента (или страницы) не меняется несколько кадров подряд.
  async settle(locator) {
    const probe = (el) => new Promise((resolve) => {
      let last = ''
      let same = 0
      const started = performance.now()
      const tick = () => {
        const r = el ? el.getBoundingClientRect() : { top: window.scrollY, left: window.scrollX }
        const key = `${Math.round(r.top)}:${Math.round(r.left)}`
        same = key === last ? same + 1 : 0
        last = key
        if (same >= 8 || performance.now() - started > 3000) resolve()
        else requestAnimationFrame(tick)
      }
      requestAnimationFrame(tick)
    })
    if (locator) await locator.evaluate(probe)
    else await this.page.evaluate(probe, null)
    await this.page.waitForTimeout(150)
  }

  async moveTo(locator, { dx = 0, dy = 0 } = {}) {
    await this.centerOn(locator)
    const box = await locator.boundingBox()
    if (!box) throw new Error(`Нет координат у ${locator}`)
    const x = Math.round(box.x + Math.min(box.width / 2, 120) + dx)
    const y = Math.round(box.y + box.height / 2 + dy)
    const dist = Math.hypot(x - this.mouse.x, y - this.mouse.y)
    const steps = Math.max(8, Math.min(35, Math.round(dist / 30)))
    await this.page.mouse.move(x, y, { steps })
    this.mouse = { x, y }
    return { x, y }
  }

  async click(locator, { hold = 600 } = {}) {
    const { x, y } = await this.moveTo(locator)
    await this.page.waitForTimeout(150)
    await this.page.mouse.click(x, y)
    if (hold) await this.page.waitForTimeout(hold)
  }

  async type(locator, text, { delay = 55, clear = true } = {}) {
    await this.click(locator, { hold: 150 })
    if (clear) await locator.fill('')
    await locator.pressSequentially(String(text), { delay })
    await this.page.waitForTimeout(250)
  }

  // Поля date/datetime-local и числа, которые нужно заменить целиком: значение вставляется сразу.
  async fill(locator, value) {
    await this.click(locator, { hold: 200 })
    await locator.fill(String(value))
    await this.page.waitForTimeout(400)
  }

  // Выпадающий список браузера не попадает в запись: показываем клик кольцом и выбираем значение.
  async select(locator, option) {
    const { x, y } = await this.moveTo(locator)
    await this.page.evaluate(([px, py]) => window.__demoRing?.(px, py), [x, y])
    await this.page.waitForTimeout(250)
    await locator.selectOption(option)
    await this.page.waitForTimeout(700)
  }

  async scrollBy(dy, ms = 600) {
    await this.page.evaluate((top) => window.scrollBy({ top, behavior: 'smooth' }), dy)
    await this.settle()
    await this.page.waitForTimeout(ms)
  }

  async scrollTop(ms = 300) {
    await this.page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
    await this.settle()
    await this.page.waitForTimeout(ms)
  }

  async banner(text, ms = 1800) {
    await this.page.evaluate((t) => window.__demoBanner?.(t), text)
    await this.page.waitForTimeout(ms)
    await this.page.evaluate(() => window.__demoBanner?.(null))
  }

  // Нативный confirm() не попадает в запись, а пока он открыт, Chromium не отдаёт кадры (видео «замирает»).
  // Поэтому только в браузере записи confirm подменяется: запоминает вопрос и отвечает «OK»; вопрос показывается плашкой.
  async clickConfirm(locator) {
    await this.page.evaluate(() => {
      window.__lastConfirm = null
      window.confirm = (message) => { window.__lastConfirm = String(message); return true }
    })
    await this.click(locator, { hold: 100 })
    const question = await this.page.waitForFunction(() => window.__lastConfirm).then((h) => h.jsonValue())
    await this.banner(`Подтверждение браузера: «${question}» → OK`, 2600)
  }

  // Ссылка из письма: в console-режиме почты backend печатает письмо в лог.
  async mailLink(email, kind) {
    const logFile = path.join(WORK_DIR, 'backend.log')
    for (let i = 0; i < 50; i++) {
      try { execFileSync(path.join(DEMO_DIR, 'scripts/stack.sh'), ['logs'], { stdio: 'ignore' }) } catch {}
      const text = readFileSync(logFile, 'utf8')
      const linkRe = new RegExp(`https?://\\S+/${kind}\\?token=[\\w\\-.~%]+`)
      const blocks = text.split('Письмо для ').filter((b) => b.startsWith(`${email}:`) && linkRe.test(b))
      if (blocks.length) {
        const url = new URL(blocks.at(-1).match(linkRe)[0])
        return url.pathname + url.search
      }
      await this.page.waitForTimeout(200)
    }
    throw new Error(`Письмо ${kind} для ${email} не найдено в логе backend`)
  }
}
