#!/usr/bin/env python3
"""Сборка курсовой работы одной командой:  python report/build_report.py

копия «Шаблона КР» → analyze_template.py → перенос и заполнение титула из шаблона курсовой →
диаграммы → контент (BlockFactory + blocks_ext) → insert_into_doc (replace) → починка TOC →
упаковка → проверки (build/verify.py). Скриншоты снимаются отдельно: build/capture.py.
"""
import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parent
BUILD = REPORT / "build"
ASSETS = REPORT / "assets"
SKILL = ROOT / "unik-report" / "scripts"
TEMPLATE_KR = ROOT / "docs" / "templates" / "Шаблон КР.docx"
TEMPLATE_KURS = ROOT / "docs" / "templates" / "Шаблон Курсовой работы (НЕ ПО СТО).docx"
OUT = REPORT / "Курсовая_работа.docx"
sys.path[:0] = [str(BUILD), str(SKILL), str(REPORT)]

import insert_into_doc  # noqa: E402
from blocks_ext import NO_INDENT, ExtBlockFactory  # noqa: E402
from build_blocks import _ppr, _run  # noqa: E402
from content import analogs, back, front, interface, part1, part2  # noqa: E402
from content.data_model import ENTITIES, ORDER  # noqa: E402
from content.references import SOURCES  # noqa: E402
from docx_post import enable_update_fields, fix_toc  # noqa: E402
from schema import parse_models  # noqa: E402
from title import transfer_title  # noqa: E402

STUDENT = {
    "topic": back.TOPIC,
    "fio": "Рубец Кирилл Сергеевич",
    "fio_dative": "Рубцу Кириллу Сергеевичу",
    "course": "3",
    "group": "521428",
}

FIG_ITEMS = {"fig", "fig_placeholder"}
TABLE_ITEMS = {"table", "rooms_table", "entities_table", "fields_table"}
REF_RE = re.compile(r"\{(fig|tab|ref):([\w]+)\}")


# --------------------------------------------------------------------------------------------- #
# Секреты в приложениях
# --------------------------------------------------------------------------------------------- #

SECRET_KEY = r"[A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_KEY|DATABASE_URL)(?!_MIN_LENGTH)[A-Z0-9_]*"


def mask_secrets(text: str, suffix: str) -> str:
    # Строки подключения с логином и паролем — в любом файле.
    text = re.sub(r"\b[a-z][a-z0-9+.-]*://[^\s'\"/@]*:[^\s'\"@]*@[^\s'\"]*", "***", text)
    if suffix in {".yml", ".yaml", ".env", ".example", ".ini"}:
        # Значения переменных-секретов в конфигурации: KEY: value / KEY=value.
        text = re.sub(rf"^(\s*-?\s*{SECRET_KEY}\s*[:=])[ \t]*\S.*$", r"\1 ***", text, flags=re.M)
    else:
        # Значения по умолчанию у os.getenv("..._PASSWORD", "литерал").
        text = re.sub(rf"(getenv\(\s*\"{SECRET_KEY}\"\s*,\s*)\"[^\"]*\"", r'\1"***"', text)
    return text


# --------------------------------------------------------------------------------------------- #
# Нумерация рисунков, таблиц и источников
# --------------------------------------------------------------------------------------------- #

def _texts(item) -> list[str]:
    kind = item[0]
    if kind == "p":
        return [item[1]]
    if kind in ("nlist", "blist"):
        return list(item[1])
    if kind == "table":
        return [c for row in item[4] for c in row]
    return []


def number(items: list) -> dict:
    """Номера по порядку появления; заодно проверка, что ссылка в тексте стоит до рисунка/таблицы."""
    nums = {"fig": {}, "tab": {}, "ref": {}}
    mentioned: set[tuple[str, str]] = set()
    for item in items:
        if item[0] in FIG_ITEMS:
            assert ("fig", item[1]) in mentioned, f"рисунок {item[1]} не упомянут в тексте до него"
            nums["fig"][item[1]] = len(nums["fig"]) + 1
        elif item[0] in TABLE_ITEMS:
            assert ("tab", item[1]) in mentioned, f"таблица {item[1]} не упомянута в тексте до неё"
            nums["tab"][item[1]] = len(nums["tab"]) + 1
        for text in _texts(item):
            for kind, key in REF_RE.findall(text):
                mentioned.add((kind, key))
                if kind == "ref" and key not in nums["ref"]:
                    assert key in SOURCES, f"нет источника {key}"
                    nums["ref"][key] = len(nums["ref"]) + 1
    missing = set(SOURCES) - set(nums["ref"])
    assert not missing, f"источники без ссылок в тексте: {sorted(missing)}"
    return nums


def resolve(text: str, nums: dict) -> str:
    def sub(m):
        kind, key = m.groups()
        if key not in nums[kind]:
            raise SystemExit(f"неизвестная ссылка {{{kind}:{key}}}")
        return str(nums[kind][key])
    return REF_RE.sub(sub, text)


# --------------------------------------------------------------------------------------------- #
# Данные для таблиц из кода
# --------------------------------------------------------------------------------------------- #

def seed_rooms() -> list[dict]:
    tree = ast.parse((ROOT / "backend" / "seed.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "ROOMS")
    return ast.literal_eval(node.value)


def _tables():
    by_name = {t.name: t for t in parse_models()}
    return [by_name[n] for n in ORDER]


def entities_rows() -> list[list[str]]:
    rows = []
    for t in _tables():
        ent, desc, cols = ENTITIES[t.name]
        for c in t.columns:
            rows.append([ent, desc, cols[c.name][0], "Да" if c.pk or c.unique else "Нет",
                         "Нет" if c.nullable else "Да"])
    return rows


def fields_rows() -> list[list[str]]:
    rows = []
    for t in _tables():
        _, _, cols = ENTITIES[t.name]
        for c in t.columns:
            desc = cols[c.name][1]
            if c.pk:
                desc += " (первичный ключ)"
            elif c.fk:
                desc += f" (внешний ключ на {c.fk.split('.')[0]})"
            # U+200B после «_»: длинные имена могут переноситься, не раздувая столбцы.
            rows.append([t.name.replace("_", "_\u200b"), c.name.replace("_", "_\u200b"), c.pg_type, c.size, desc,
                         "Да" if c.pk or c.unique else "Нет"])
    return rows


# --------------------------------------------------------------------------------------------- #
# Отрисовка элементов контента
# --------------------------------------------------------------------------------------------- #

def render(item, b: ExtBlockFactory, nums: dict) -> str:
    kind = item[0]
    if kind == "structural":
        return b.structural(item[1])
    if kind in ("h1", "h2", "h3"):
        return b.heading(int(kind[1]), item[1])
    if kind == "p":
        return b.paragraph(resolve(item[1], nums))
    if kind == "nlist":
        return b.numbered_list([resolve(t, nums) for t in item[1]])
    if kind == "blist":
        return b.bullet_list([resolve(t, nums) for t in item[1]])
    if kind == "abbreviations":
        return "".join(b.paragraph(f"{a} – {d}", no_indent=True) for a, d in item[1])
    if kind == "fig":
        opts = item[4] if len(item) > 4 else {}
        img = b.figure_image(ASSETS / item[2], width_cm=opts.get("width", 16.5), crop_ratio=opts.get("crop"),
                             max_height_cm=opts.get("max_h", 21.5))
        return img + b.figure_caption(item[3])
    if kind == "fig_placeholder":
        return b.figure_placeholder(item[2], height_cm=8, width_cm=16) + b.figure_caption(item[3])
    if kind == "table":
        caption, headers, rows = item[2], item[3], item[4]
        return b.data_table(caption, headers, [[resolve(c, nums) for c in r] for r in rows])
    if kind == "rooms_table":
        rows = [[r["name"], str(r["capacity"]), str(r["area"]), f'{r["price_per_night"]:,}'.replace(",", " "),
                 ", ".join(r["amenities"])] for r in seed_rooms()]
        return b.data_table(item[2], ["Категория", "Вмести\u00adмость, чел.", "Площадь, м²", "Цена за ночь, руб.",
                                      "Удобства"], rows)
    if kind == "entities_table":
        return b.data_table(item[2], ["Наимено\u00adвание сущности", "Описание сущности", "Наимено\u00adвание атрибута",
                                      "Уникаль\u00adность атрибута", "Обязатель\u00adность атрибута"],
                            entities_rows(), merge_cols=(0, 1))
    if kind == "fields_table":
        return b.data_table(item[2], ["Наимено\u00adвание таблицы", "Имя поля", "Тип данных", "Размер", "Описание",
                                      "Уникаль\u00adность"],
                            fields_rows(), merge_cols=(0,))
    if kind == "references":
        order = sorted(nums["ref"], key=nums["ref"].get)
        return b.references([SOURCES[k] for k in order])
    raise SystemExit(f"неизвестный элемент контента: {kind}")


def render_appendices(b: ExtBlockFactory) -> str:
    out = []
    for letter, title, listings in back.APPENDICES:
        out.append(b.structural(f"ПРИЛОЖЕНИЕ {letter}"))
        out.append(b.centered("(обязательное)"))
        out.append(b.centered(title, bold=True))
        for i, (caption, rel) in enumerate(listings, 1):
            path = ROOT / rel
            code = mask_secrets(path.read_text(encoding="utf-8"), path.suffix or path.name)
            out.append(b.appendix_listing(f"{letter}.{i}", caption, code.rstrip("\n")))
    return "".join(out)


def render_self_check(b: ExtBlockFactory) -> str:
    sc = back.SELF_CHECK
    title_ppr = _ppr(style_id=b.s["body"], page_break_before=True, indent=NO_INDENT, jc="center")
    out = [f"<w:p>{title_ppr}{_run(sc['title'], '<w:rPr><w:b/></w:rPr>')}</w:p>"]
    out += [b.paragraph(p) for p in sc["paragraphs"]]
    out.append(b.paragraph(""))
    out.append(b.paragraph(sc["signature"], no_indent=True))
    hint_ppr = _ppr(style_id=b.s["body"], indent='<w:ind w:left="4253" w:firstLine="0"/>')
    out.append(f"<w:p>{hint_ppr}{_run(sc['signature_hint'], '<w:rPr><w:sz w:val=\"20\"/></w:rPr>')}</w:p>")
    return "".join(out)


def content_items() -> list:
    return (front.NORMATIVE + front.DEFINITIONS + front.INTRODUCTION
            + part1.OBJECT + analogs.ANALOGS + part1.TOOLS
            + part2.LOGICAL + part2.PHYSICAL + part2.PROJECT + interface.INTERFACE
            + back.CONCLUSION + back.REFERENCES)


# --------------------------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-diagrams", action="store_true", help="не перерисовывать диаграммы (взять готовые PNG)")
    args = ap.parse_args()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")

    # 1. Копия «Шаблона КР», распаковка и анализ стилей.
    template = BUILD / "template.docx"
    unpacked = BUILD / "unpacked"
    shutil.copyfile(TEMPLATE_KR, template)
    shutil.rmtree(unpacked, ignore_errors=True)
    with open(BUILD / "analyze.json", "w", encoding="utf-8") as f:
        subprocess.run([sys.executable, str(SKILL / "analyze_template.py"), str(template), str(unpacked)],
                       check=True, stdout=f, env=env)
    style_map = json.loads((BUILD / "style_map.json").read_text(encoding="utf-8"))
    need = ["heading_1", "heading_2", "heading_3", "structural", "figure_body", "figure_caption", "listing_body",
            "listing_caption", "table_caption", "table_header", "bullet_list", "numbered_list",
            "references_list", "body", "toc_1", "toc_2", "toc_3"]
    absent = [r for r in need if not style_map.get(r)]
    assert not absent, f"в style_map нет ролей: {absent}"

    # 2. Титульный лист и лист задания из шаблона курсовой.
    transfer_title(TEMPLATE_KURS, unpacked, STUDENT)

    # 3. Диаграммы.
    if not args.skip_diagrams:
        import diagrams
        diagrams.render_all()

    # 4. Контент.
    b = ExtBlockFactory(style_map, unpacked)
    items = content_items()
    nums = number(items)
    xml = "".join(render(it, b, nums) for it in items) + render_appendices(b) + render_self_check(b)
    (BUILD / "content.xml").write_text(xml, encoding="utf-8")
    (BUILD / "numbers.json").write_text(json.dumps(nums, ensure_ascii=False, indent=1), encoding="utf-8")

    # 5. Вставка скриптом скилла, починка оглавления, упаковка.
    insert_into_doc.insert_content(unpacked, xml, mode="replace")
    b.flush()
    fix_toc(unpacked, {style_map["toc_1"], style_map["toc_2"], style_map["toc_3"]})
    enable_update_fields(unpacked)
    insert_into_doc.pack_and_validate(unpacked, OUT, validate=False)

    # 6. Проверки; схемная проверка OOXML — validate.py docx-скилла, если путь к нему задан.
    import verify
    verify.run(OUT, nums, items)
    if os.environ.get("DOCX_VALIDATOR"):
        subprocess.run([sys.executable, os.environ["DOCX_VALIDATOR"], str(OUT)], check=True, env=env)


if __name__ == "__main__":
    main()
