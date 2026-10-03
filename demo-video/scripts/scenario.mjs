// Разбор таблицы SCENARIO.md: одна строка — один шаг сцены и его субтитр.
import { readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { DEMO_DIR } from './lib.mjs'

export const SCENARIO_FILE = path.join(DEMO_DIR, 'SCENARIO.md')
const START = '<!-- scenario:table:start -->'
const END = '<!-- scenario:table:end -->'

export const SCENE_ORDER = ['K1', 'K2', 'K3', 'K4', 'K5', 'K6', 'K7', 'K8', 'A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8']

function cells(line) {
  return line.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
}

export function readScenario() {
  const text = readFileSync(SCENARIO_FILE, 'utf8')
  const body = text.slice(text.indexOf(START) + START.length, text.indexOf(END))
  const lines = body.split('\n').filter((l) => l.trim().startsWith('|'))
  const header = cells(lines[0])
  return lines.slice(2).map((line) => {
    const c = cells(line)
    const row = Object.fromEntries(header.map((h, i) => [h, c[i] ?? '']))
    return { id: row.ID, scene: row['Сцена'], role: row['Роль'], func: row['Функция'], steps: row['Шаги'], subtitle: row['Субтитр'], timecode: row['Таймкод'] }
  })
}

export function stepsOf(sceneId) {
  return readScenario().filter((r) => r.scene === sceneId).map((r) => r.id)
}

// Записывает таймкоды в колонку «Таймкод» и таблицу сцен (между маркерами scenario:scenes).
export function writeTimecodes(stepTimes, sceneRows) {
  let text = readFileSync(SCENARIO_FILE, 'utf8')
  const head = text.slice(0, text.indexOf(START) + START.length)
  const tail = text.slice(text.indexOf(END))
  const body = text.slice(head.length, text.indexOf(END))
  const newBody = body.split('\n').map((line) => {
    if (!line.trim().startsWith('|')) return line
    const c = cells(line)
    if (!stepTimes[c[0]]) return line
    c[c.length - 1] = stepTimes[c[0]]
    return `| ${c.join(' | ')} |`
  }).join('\n')
  text = head + newBody + tail

  const S = '<!-- scenario:scenes:start -->'
  const E = '<!-- scenario:scenes:end -->'
  const table = [
    S,
    '| Сцена | Раздел | Начало в full.mp4 | Длительность |',
    '|---|---|---|---|',
    ...sceneRows.map((r) => `| ${r.scene} | ${r.section} | ${r.start} | ${r.duration} |`),
    E,
  ].join('\n')
  if (text.includes(S)) {
    text = text.slice(0, text.indexOf(S)) + table + text.slice(text.indexOf(E) + E.length)
  } else {
    text = text.replace(START, `## Таймкоды сцен в out/full.mp4\n\n${table}\n\n## Шаги и субтитры\n\n${START}`)
  }
  writeFileSync(SCENARIO_FILE, text)
}
