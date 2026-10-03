import { spawnSync } from 'node:child_process'

// Метки шагов в кадре (см. Demo.step): квадрат 12×12 в левом нижнем углу меняет цвет красный ↔ синий.
// Возвращает время каждой смены цвета в видео: N шагов + конец сцены. Дрейф часов записи на них не влияет.
export function videoMarks(raw, expected) {
  const res = spawnSync('ffmpeg', ['-hide_banner', '-i', raw, '-vf', 'crop=8:8:6:1066,showinfo', '-f', 'null', '-'], { encoding: 'utf8', maxBuffer: 1 << 28 })
  const times = []
  let last = null
  for (const line of res.stderr.split('\n')) {
    const pts = line.match(/pts_time:([\d.]+)/)
    const mean = line.match(/mean:\[(\d+) (\d+) (\d+)\]/)
    if (!pts || !mean) continue
    const [u, v] = [Number(mean[2]), Number(mean[3])]
    const color = v > 200 && u < 140 ? 'red' : u > 200 && v < 150 ? 'blue' : null
    if (color && color !== last) {
      times.push(Number(pts[1]))
      last = color
    }
  }
  if (times.length !== expected) throw new Error(`${raw}: найдено меток ${times.length}, ожидалось ${expected} — перезапишите сцену`)
  return times
}
