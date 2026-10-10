// Запись сцен: отдельный контекст браузера и отдельный файл видео на каждую сцену.
// Перед сценой — снимок БД; упавшая сцена откатывает БД к снимку и перезаписывается целиком (до 3 попыток).
//
//   node scripts/record.mjs            — все сцены по порядку
//   node scripts/record.mjs K1 A1      — только указанные
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'
import { DEMO_DIR, Demo, RAW_DIR, VIEWPORT, WORK_DIR } from './lib.mjs'
import { SCENE_ORDER, stepsOf } from './scenario.mjs'
import { videoMarks } from './video.mjs'
import { scenes as clientScenes } from './scenes/client.mjs'
import { scenes as adminScenes } from './scenes/admin.mjs'

const SCENES = { ...clientScenes, ...adminScenes }
const MAX_ATTEMPTS = Number(process.env.MAX_ATTEMPTS || 3)
const SLOW_MO = Number(process.env.SLOW_MO || 300)
const SYSTEM_CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'

const stack = (...args) => execFileSync(path.join(DEMO_DIR, 'scripts/stack.sh'), args, { stdio: 'inherit' })
const statePath = (name) => path.join(WORK_DIR, `state-${name}.json`)

async function recordScene(browser, id) {
  const scene = SCENES[id]
  const expected = stepsOf(id)
  const tmpDir = path.join(WORK_DIR, 'video-tmp', id)
  rmSync(tmpDir, { recursive: true, force: true })

  if (scene.state && !existsSync(statePath(scene.state))) {
    throw new Error(`${id}: нет сохранённой сессии «${scene.state}» — сначала запишите сцену, которая её создаёт`)
  }
  const context = await browser.newContext({
    viewport: VIEWPORT,
    screen: VIEWPORT,
    deviceScaleFactor: 1,
    locale: 'ru-RU',
    timezoneId: 'Europe/Moscow',
    recordVideo: { dir: tmpDir, size: VIEWPORT },
    storageState: scene.state ? statePath(scene.state) : undefined,
  })
  await Demo.install(context)
  const page = await context.newPage()
  page.setDefaultTimeout(20000)
  const demo = new Demo(page, id)
  try {
    const sync = await demo.syncFlash()
    await scene.run(demo)
    const end = await demo.endMark()
    const got = demo.marks.map((m) => m.id)
    if (got.join() !== expected.join()) {
      throw new Error(`${id}: шаги ${got.join(',')} не совпадают со SCENARIO.md (${expected.join(',')})`)
    }
    if (scene.saveState) await context.storageState({ path: statePath(scene.saveState) })
    const video = page.video()
    await context.close()
    mkdirSync(RAW_DIR, { recursive: true })
    const rawFile = path.join(RAW_DIR, `${id}.webm`)
    renameSync(await video.path(), rawFile)
    // Каждая метка шага должна найтись в кадре, иначе субтитры не синхронизировать — сцена перезаписывается.
    videoMarks(rawFile, demo.marks.length + 1)
    writeFileSync(path.join(RAW_DIR, `${id}.json`), JSON.stringify({ id, sync, marks: demo.marks, end }, null, 2))
    return end
  } catch (error) {
    await page.screenshot({ path: path.join(WORK_DIR, `fail-${id}.png`) }).catch(() => {})
    await context.close().catch(() => {})
    throw error
  }
}

async function main() {
  const ids = process.argv.slice(2).length ? process.argv.slice(2) : SCENE_ORDER
  for (const id of ids) if (!SCENES[id]) throw new Error(`Неизвестная сцена ${id}`)
  mkdirSync(WORK_DIR, { recursive: true })

  const browser = await chromium.launch({
    slowMo: SLOW_MO,
    executablePath: existsSync(SYSTEM_CHROMIUM) ? SYSTEM_CHROMIUM : undefined,
    args: ['--hide-scrollbars', '--force-device-scale-factor=1', '--lang=ru-RU'],
    env: { ...process.env, LANG: 'ru_RU.UTF-8', LANGUAGE: 'ru_RU:ru' }, // формат дат в полях type=date — русский
  })
  const summary = []
  try {
    for (const id of ids) {
      stack('snapshot', `pre-${id}`)
      for (let attempt = 1; ; attempt++) {
        console.log(`▶ ${id}: попытка ${attempt}`)
        try {
          const seconds = await recordScene(browser, id)
          summary.push({ id, seconds: seconds.toFixed(1), attempts: attempt })
          console.log(`✔ ${id}: ${seconds.toFixed(1)} с`)
          break
        } catch (error) {
          console.error(`✘ ${id}: ${error.message.split('\n').slice(0, 6).join(' | ')}`)
          if (attempt >= MAX_ATTEMPTS) throw new Error(`Сцена ${id} не записалась за ${MAX_ATTEMPTS} попытки`)
          stack('restore', `pre-${id}`) // сломанное видео не сохраняется, БД возвращается к состоянию до сцены
        }
      }
    }
  } finally {
    await browser.close()
    console.table(summary)
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
