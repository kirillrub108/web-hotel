// Монтаж: титульные карточки (lavfi color + drawtext) → сцены клиента → сцены администратора → финальная карточка.
// Субтитры — из SCENARIO.md в формате ASS, вшиваются в кадр. Выход: H.264, yuv420p, 30 fps, CRF 26, faststart.
//
//   node scripts/build.mjs                 — out/client.mp4, out/admin.mp4, out/full.mp4 + таймкоды в SCENARIO.md
//   node scripts/build.mjs --pilot K1 A1   — work/pilot.mp4 из указанных сцен (проверка перед полной записью)
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { DEMO_DIR, RAW_DIR, WORK_DIR } from './lib.mjs'
import { SCENE_ORDER, readScenario, writeTimecodes } from './scenario.mjs'
import { videoMarks } from './video.mjs'

const OUT_DIR = path.join(DEMO_DIR, 'out')
const CLIPS = path.join(WORK_DIR, 'clips')
const FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
const FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
const FPS = 30
const X264 = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '26', '-pix_fmt', 'yuv420p', '-r', String(FPS),
  '-profile:v', 'high', '-video_track_timescale', '15360', '-an']
const LEAD_IN = 0.4 // секунды до первого шага (страница уже загружена)
const FADE = 0.3

const run = (args) => execFileSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', ...args], { stdio: 'inherit' })
const duration = (file) => Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file]).toString())

function assTime(sec) {
  const cs = Math.max(0, Math.round(sec * 100))
  const h = Math.floor(cs / 360000)
  const m = Math.floor((cs % 360000) / 6000)
  const s = Math.floor((cs % 6000) / 100)
  return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(cs % 100).padStart(2, '0')}`
}

function clock(sec) {
  const s = Math.round(sec)
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

// Субтитр внизу по центру на полупрозрачной плашке; нижние 160 px кадра сценарии не используют для действий.
function writeAss(file, events) {
  const header = `[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,DejaVu Sans,38,&H00FFFFFF,&H00FFFFFF,&H40141414,&H40141414,0,0,0,0,100,100,0,0,3,14,0,2,200,200,34,204
Style: Tag,DejaVu Sans,24,&H00FFFFFF,&H00FFFFFF,&H30285AFF,&H30285AFF,1,0,0,0,100,100,0,0,3,8,0,7,30,30,20,204

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`
  const lines = events.map((e) => `Dialogue: 0,${assTime(e.start)},${assTime(e.end)},${e.style || 'Sub'},,0,0,0,,${e.text.replace(/\n/g, '\\N')}`)
  writeFileSync(file, header + lines.join('\n') + '\n')
}

// Сцена: обрезка «мёртвых» пауз (загрузка до первого шага), субтитры по меткам шагов, лёгкие fade на стыках.
function renderScene(id, rows) {
  const meta = JSON.parse(readFileSync(path.join(RAW_DIR, `${id}.json`), 'utf8'))
  const raw = path.join(RAW_DIR, `${id}.webm`)
  const marks = videoMarks(raw, meta.marks.length + 1)
  const start = Math.max(0, marks[0] - LEAD_IN)
  const end = marks.at(-1)
  const len = end - start
  const subtitle = Object.fromEntries(rows.map((r) => [r.id, r]))
  const events = meta.marks.map((m, i) => ({ id: m.id, start: marks[i] - start, end: marks[i + 1] - start, text: subtitle[m.id].subtitle }))
  console.log(`  длительность ${len.toFixed(1)} с (запись ${meta.end.toFixed(1)} с)`)
  const tagText = `${id.startsWith('K') ? 'Клиент' : 'Администратор'} · сцена ${id}`
  const assEvents = [...events, { start: 0, end: len, style: 'Tag', text: tagText }]
  const ass = path.join(CLIPS, `${id}.ass`)
  writeAss(ass, assEvents)
  const out = path.join(CLIPS, `${id}.mp4`)
  run(['-ss', start.toFixed(3), '-i', raw, '-t', len.toFixed(3),
    '-vf', `delogo=x=1:y=1061:w=20:h=18,fps=${FPS},scale=1920:1080,setsar=1,ass=${ass},fade=t=in:st=0:d=${FADE},fade=t=out:st=${(len - FADE).toFixed(3)}:d=${FADE},format=yuv420p`,
    ...X264, out])
  return { id, file: out, duration: duration(out), events }
}

function drawtext(text, { size, y, bold = false, color = 'white' }) {
  const escaped = text.replace(/\\/g, '\\\\').replace(/:/g, '\\:').replace(/'/g, "\u2019").replace(/%/g, '\\%')
  return `drawtext=fontfile=${bold ? FONT_BOLD : FONT}:text='${escaped}':fontsize=${size}:fontcolor=${color}:x=(w-text_w)/2:y=${y}`
}

function renderCard(name, lines, seconds) {
  const out = path.join(CLIPS, `card-${name}.mp4`)
  const filters = [
    'drawbox=x=(iw-360)/2:y=600:w=360:h=6:color=0xff5a28@1:t=fill',
    ...lines.map((l) => drawtext(l.text, l)),
    `fade=t=in:st=0:d=0.5,fade=t=out:st=${seconds - 0.5}:d=0.5`,
    'format=yuv420p',
  ]
  run(['-f', 'lavfi', '-i', `color=c=0x1f2937:s=1920x1080:r=${FPS}:d=${seconds}`, '-vf', filters.join(','), ...X264, out])
  return { id: `card-${name}`, file: out, duration: duration(out) }
}

function concat(parts, out) {
  const list = path.join(CLIPS, `${path.basename(out)}.txt`)
  writeFileSync(list, parts.map((p) => `file '${p.file}'`).join('\n') + '\n')
  const tmp = `${out}.tmp.mp4`
  run(['-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', '-movflags', '+faststart', tmp])
  renameSync(tmp, out)
  return duration(out)
}

function main() {
  mkdirSync(CLIPS, { recursive: true })
  mkdirSync(OUT_DIR, { recursive: true })
  const rows = readScenario()
  const args = process.argv.slice(2)
  const pilot = args[0] === '--pilot'
  const ids = pilot ? args.slice(1) : SCENE_ORDER
  for (const id of ids) {
    if (!existsSync(path.join(RAW_DIR, `${id}.json`))) throw new Error(`Нет записи сцены ${id}: запустите record.mjs`)
  }

  const scenes = Object.fromEntries(ids.map((id) => {
    console.log(`• сцена ${id}`)
    return [id, renderScene(id, rows)]
  }))

  const title = renderCard('title', [
    { text: 'Kivana', size: 120, y: 330, bold: true },
    { text: 'Веб-приложение гостиницы: бронирование, личный кабинет, админка', size: 40, y: 500 },
    { text: 'Демонстрация функционала · курсовой проект', size: 34, y: 650, color: '0xcbd5e1' },
  ], 3)
  const clientCard = renderCard('client', [
    { text: 'Функционал клиента', size: 92, y: 420, bold: true },
    { text: 'каталог · регистрация · бронирование · личный кабинет', size: 36, y: 650, color: '0xcbd5e1' },
  ], 2.5)
  const adminCard = renderCard('admin', [
    { text: 'Функционал администратора', size: 92, y: 420, bold: true },
    { text: 'заявки · клиенты · номера · акции · услуги · заказы · уборка', size: 36, y: 650, color: '0xcbd5e1' },
  ], 2.5)
  const finalCard = renderCard('final', [
    { text: 'Спасибо за внимание', size: 92, y: 400, bold: true },
    { text: 'Kivana · FastAPI · PostgreSQL · Nuxt', size: 40, y: 650, color: '0xcbd5e1' },
  ], 3)

  const clientIds = ids.filter((id) => id.startsWith('K'))
  const adminIds = ids.filter((id) => id.startsWith('A'))
  const clientParts = [clientCard, ...clientIds.map((id) => scenes[id])]
  const adminParts = [adminCard, ...adminIds.map((id) => scenes[id])]
  const fullParts = [title, ...clientParts, ...adminParts, finalCard]

  if (pilot) {
    const total = concat(fullParts, path.join(WORK_DIR, 'pilot.mp4'))
    console.log(`work/pilot.mp4: ${total.toFixed(1)} с`)
    return
  }

  const clientLen = concat(clientParts, path.join(OUT_DIR, 'client.mp4'))
  const adminLen = concat(adminParts, path.join(OUT_DIR, 'admin.mp4'))
  const fullLen = concat(fullParts, path.join(OUT_DIR, 'full.mp4'))

  // Таймкоды по фактическим длительностям клипов в full.mp4.
  const stepTimes = {}
  const sceneRows = []
  let t = 0
  for (const part of fullParts) {
    const scene = scenes[part.id]
    if (scene) {
      for (const e of scene.events) stepTimes[e.id] = clock(t + e.start)
      sceneRows.push({ scene: part.id, section: part.id.startsWith('K') ? 'Клиент' : 'Администратор', start: clock(t), duration: `${part.duration.toFixed(1)} с` })
    }
    t += part.duration
  }
  writeTimecodes(stepTimes, sceneRows)
  console.log(`client.mp4 ${clientLen.toFixed(1)} с · admin.mp4 ${adminLen.toFixed(1)} с · full.mp4 ${fullLen.toFixed(1)} с`)
  console.table(sceneRows)
}

main()
