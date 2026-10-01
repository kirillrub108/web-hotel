#!/usr/bin/env python3
"""
insert_into_doc.py — вставляет сгенерированный XML-контент в распакованный
шаблон САФУ и упаковывает обратно в .docx.

Использование:
    python3 insert_into_doc.py \
        --unpacked /path/to/unpacked \
        --content /path/to/content.xml \
        --output  /path/to/filled.docx \
        [--mode replace|append] \
        [--original /path/to/template.docx]

Режимы:
    replace — заменить всё тело (после титульника/задания/оглавления) на
              новый контент. Это вариант по умолчанию.
    append  — дописать контент в конец тела, перед последним <w:sectPr>,
              ничего не удаляя.

При insert_into_doc.py НЕ трогается:
    - всё, что выше точки body_start_offset (титульник, лист задания, ТОС);
    - финальный <w:sectPr> страницы — иначе слетят колонтитулы и поля;
    - sections.xml, headers/footers, numbering, styles, theme, relationships.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


def _docx_office_script(name: str) -> Optional[Path]:
    """Ищет скрипт docx-скилла: /mnt (штатное окружение), затем соседний установленный скилл docx."""
    for base in (Path("/mnt/skills/public/docx/scripts/office"),
                 Path(__file__).resolve().parents[2] / "docx" / "scripts" / "office"):
        if (base / name).exists():
            return base / name
    return None


PACK_SCRIPT = _docx_office_script("pack.py")
VALIDATE_SCRIPT = _docx_office_script("validate.py")


# --------------------------------------------------------------------------- #
# Импорт find_body_start из analyze_template.py (если рядом) — но дублируем,
# чтобы insert_into_doc.py был самодостаточным.
# --------------------------------------------------------------------------- #

def _iter_paragraphs(doc_xml: str):
    for m in re.finditer(r"<w:p\b[^>]*>(?:(?!<w:p\b).)*?</w:p>", doc_xml, re.DOTALL):
        yield m.start(), m.end(), m.group(0)


def _extract_text(p_xml: str) -> str:
    parts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", p_xml, re.DOTALL)
    return "".join(parts).strip()


def find_body_start(doc_xml: str, style_map: dict) -> int:
    toc_ids = {style_map.get("toc_1"), style_map.get("toc_2"), style_map.get("toc_3")}
    toc_ids.discard(None)
    p_list = list(_iter_paragraphs(doc_xml))

    candidate: int

    for i, (_, end, p) in enumerate(p_list):
        text = _extract_text(p).upper()
        if "ОГЛАВЛЕНИЕ" in text or "СОДЕРЖАНИЕ" in text:
            j = i + 1
            while j < len(p_list):
                nxt_p = p_list[j][2]
                ps = re.search(r'<w:pStyle\s+w:val="([^"]+)"', nxt_p)
                if ps and ps.group(1) in toc_ids:
                    j += 1
                else:
                    break
            if j < len(p_list):
                candidate = p_list[j][0]
            else:
                candidate = p_list[i][1]
            return _escape_open_structures(doc_xml, candidate)

    h1 = style_map.get("heading_1")
    if h1:
        for start, _, p in p_list:
            ps = re.search(r'<w:pStyle\s+w:val="([^"]+)"', p)
            if ps and ps.group(1) == h1:
                return _escape_open_structures(doc_xml, start)

    sect = re.search(r"<w:sectPr\b", doc_xml)
    if sect:
        end_p = doc_xml.find("</w:p>", sect.end())
        if end_p != -1:
            return _escape_open_structures(doc_xml, end_p + len("</w:p>"))
    body_close = doc_xml.rfind("</w:body>")
    return body_close if body_close != -1 else len(doc_xml)


def _escape_open_structures(doc_xml: str, offset: int) -> int:
    """Гарантирует, что offset находится в «теле» <w:body>, а не внутри
    открытого <w:sdt> / <w:tbl>. Если внутри — продвигает вперёд до
    закрывающего тега ближайшей охватывающей конструкции.

    Это критично: оглавление в шаблонах САФУ часто обёрнуто в
    <w:sdt><w:sdtContent>...</w:sdtContent></w:sdt>, и точка «после
    оглавления» может оказаться до </w:sdt> — тогда вырезание тела
    оборвёт XML.
    """
    head = doc_xml[:offset]
    # Подсчёт баланса
    for tag_open, tag_close in (("<w:sdt ", "</w:sdt>"),
                                ("<w:sdt>", "</w:sdt>"),
                                ("<w:tbl ", "</w:tbl>"),
                                ("<w:tbl>", "</w:tbl>")):
        opens = head.count(tag_open)
        closes = head.count(tag_close)
        # Если открытий больше — продвинуть offset за следующее закрытие
        while opens > closes:
            nxt = doc_xml.find(tag_close, offset)
            if nxt == -1:
                # Нет закрытия — оставляем как есть, дальше упадёт валидатор
                return offset
            offset = nxt + len(tag_close)
            head = doc_xml[:offset]
            opens = head.count(tag_open)
            closes = head.count(tag_close)
    return offset


# --------------------------------------------------------------------------- #
# Поиск финального <w:sectPr> (он должен остаться нетронутым)
# --------------------------------------------------------------------------- #

def find_last_section_anchor(doc_xml: str) -> int:
    """Возвращает offset перед финальным абзацем-якорем с <w:sectPr>.

    В docx последний <w:sectPr> либо стоит прямо внутри <w:body> как
    самостоятельный элемент, либо находится внутри <w:pPr> у последнего
    параграфа документа. Нам важно сохранить его — в нём прописаны поля
    страницы, колонтитулы и пр.
    """
    last_sect = doc_xml.rfind("<w:sectPr")
    if last_sect == -1:
        # Нет sectPr — режем перед </w:body>
        return doc_xml.rfind("</w:body>")

    # Ищем границу параграфа, в котором лежит этот sectPr (или сам sectPr,
    # если он стоит прямо в body).
    # Сначала смотрим назад до ближайшего <w:p или начала body.
    head = doc_xml[:last_sect]
    open_p = head.rfind("<w:p ")
    if open_p == -1:
        open_p = head.rfind("<w:p>")

    # Если между <w:p и <w:sectPr там точно есть только <w:pPr> — это абзац-якорь
    # sectPr должен лежать ВНУТРИ этого абзаца: если между ними есть </w:p>, это
    # просто предыдущий абзац тела (например, подпись-заглушка шаблона), а sectPr — прямой ребёнок body.
    if open_p != -1 and "<w:pPr>" in doc_xml[open_p:last_sect] and "</w:p>" not in doc_xml[open_p:last_sect]:
        return open_p
    # Иначе sectPr — прямой ребёнок body, режем перед ним
    return last_sect


# --------------------------------------------------------------------------- #
# Главные операции
# --------------------------------------------------------------------------- #

def load_style_map(unpacked: Path) -> dict:
    # Сначала ищем style_map.json в родителе unpacked (его пишет analyze_template).
    candidates = [
        unpacked.parent / "style_map.json",
        unpacked / "style_map.json",
    ]
    for p in candidates:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise SystemExit(
        "style_map.json не найден. Сначала запусти analyze_template.py — "
        "он создаёт style_map.json рядом с распакованной директорией."
    )


def insert_content(
    unpacked: Path,
    content_xml: str,
    mode: str,
) -> None:
    doc_path = unpacked / "word" / "document.xml"
    doc_xml = doc_path.read_text(encoding="utf-8")

    style_map = load_style_map(unpacked)

    body_start = find_body_start(doc_xml, style_map)
    section_anchor = find_last_section_anchor(doc_xml)

    if section_anchor < body_start:
        # Странный шаблон: sectPr раньше тела. Не рискуем — пишем перед </w:body>.
        section_anchor = doc_xml.rfind("</w:body>")

    head = doc_xml[:body_start]
    middle = doc_xml[body_start:section_anchor]
    tail = doc_xml[section_anchor:]

    if mode == "replace":
        # Полностью выбрасываем middle (старое тело), вставляем новое
        new_xml = head + content_xml + tail
    elif mode == "append":
        # Дописываем в конец тела, перед sectPr-якорем
        new_xml = head + middle + content_xml + tail
    else:
        raise ValueError(f"Неизвестный режим: {mode}")

    doc_path.write_text(new_xml, encoding="utf-8")
    print(f"[ok] document.xml обновлён ({len(new_xml)} симв.). "
          f"body_start={body_start}, section_anchor={section_anchor}, mode={mode}")


def pack_and_validate(
    unpacked: Path,
    output: Path,
    original: Optional[Path] = None,
    validate: bool = True,
) -> None:
    if PACK_SCRIPT is not None:
        cmd = [sys.executable, str(PACK_SCRIPT), str(unpacked), str(output)]
        if original is not None:
            cmd.extend(["--original", str(original)])
        if not validate:
            cmd.extend(["--validate", "false"])
        subprocess.run(cmd, check=True)
    else:
        # pack.py docx-скилла недоступен — упаковываем zipfile, [Content_Types].xml первым.
        import zipfile
        files = sorted(p for p in unpacked.rglob("*") if p.is_file())
        files.sort(key=lambda p: p.name != "[Content_Types].xml")
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in files:
                zf.write(p, p.relative_to(unpacked).as_posix())
    print(f"[ok] packed → {output}")

    if validate and VALIDATE_SCRIPT is not None:
        r = subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT), str(output)],
            capture_output=True, text=True,
        )
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        if r.returncode != 0:
            print("[warn] validator finished with non-zero code — "
                  "проверь XML и пересоберите.", file=sys.stderr)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--unpacked", required=True,
                    help="Папка с распакованным шаблоном (выход analyze_template.py)")
    ap.add_argument("--content", required=True,
                    help="Файл с XML-контентом (склейка вызовов BlockFactory)")
    ap.add_argument("--output", required=True,
                    help="Путь к итоговому .docx")
    ap.add_argument("--mode", default="replace", choices=["replace", "append"],
                    help="replace — заменить тело; append — дописать в конец")
    ap.add_argument("--original",
                    help="Путь к исходному .docx (помогает pack.py сохранить "
                         "то, что он сам не пакует — например, custom XML).")
    ap.add_argument("--no-validate", action="store_true",
                    help="Пропустить вызов validate.py")
    args = ap.parse_args()

    unpacked = Path(args.unpacked).resolve()
    content_path = Path(args.content).resolve()
    output = Path(args.output).resolve()
    original = Path(args.original).resolve() if args.original else None

    if not unpacked.is_dir():
        raise SystemExit(f"Не папка: {unpacked}")
    if not content_path.is_file():
        raise SystemExit(f"Не файл: {content_path}")

    content_xml = content_path.read_text(encoding="utf-8")
    insert_content(unpacked, content_xml, mode=args.mode)
    pack_and_validate(
        unpacked,
        output,
        original=original,
        validate=not args.no_validate,
    )


if __name__ == "__main__":
    main()
