#!/usr/bin/env python3
"""
analyze_template.py — анализатор шаблона САФУ для скилла unik-report.

Распаковывает .docx, строит style_map (смысловая роль → styleId), вычленяет
заголовочную часть документа (титульник + лист задания/замечаний + оглавление),
возвращает структуру существующего отчёта и точку, после которой можно
вставлять контент.

Использование:
    python3 analyze_template.py <template.docx> <unpacked_dir>

Печатает JSON со всей метаинформацией в stdout. Также сохраняет:
    <unpacked_dir>/../style_map.json
    <unpacked_dir>/../analysis.json
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Маппинг "роль -> список кандидатов имён стилей".
# Поиск идёт по подстроке без учёта регистра, в указанном порядке.
ROLE_TO_NAMES: Dict[str, List[str]] = {
    "heading_1":        ["heading 1", "заголовок 1"],
    "heading_2":        ["heading 2", "заголовок 2"],
    "heading_3":        ["heading 3", "заголовок 3"],
    "heading_4":        ["heading 4", "заголовок 4"],
    "structural":       ["структурный элемент"],
    "figure_body":      ["иллюстрация"],
    "figure_caption":   ["подпись к иллюстрации", "подпись к рисункам", "caption"],
    "listing_body":     ["листинг"],
    "listing_caption":  ["подпись к листингу"],
    "table_caption":    ["подпись к таблице"],
    "table_header":     ["заголовок таблицы"],
    "formula":          ["формула", "equation"],
    "bullet_list":      ["list bullet", "маркированный список"],
    "numbered_list":    ["перечисление", "нумерованный список", "list number"],
    "references_list":  ["список использованных источников", "bibliography"],
    "body":             ["normal", "обычный"],
    "toc_1":            ["toc 1", "оглавление 1"],
    "toc_2":            ["toc 2", "оглавление 2"],
    "toc_3":            ["toc 3", "оглавление 3"],
}

# Эвристики типа работы по тексту титульника.
KIND_MARKERS = {
    "kr": ["контрольная работа", "контрольную работу"],
    "lp": ["лабораторный практикум"],
    "lr": ["лабораторная работа", "отчёт по лабораторной"],
}


# --------------------------------------------------------------------------- #
# Распаковка
# --------------------------------------------------------------------------- #


def _docx_office_script(name: str) -> Optional[Path]:
    """Ищет скрипт docx-скилла: /mnt (штатное окружение), затем соседний установленный скилл docx."""
    for base in (Path("/mnt/skills/public/docx/scripts/office"),
                 Path(__file__).resolve().parents[2] / "docx" / "scripts" / "office"):
        if (base / name).exists():
            return base / name
    return None


def unpack_docx(docx_path: Path, dest: Path) -> None:
    """Распаковываем шаблон стандартным скриптом docx-скилла (pretty-print + merged runs).
    Если его нет (другая ОС/установка) — обычной распаковкой zipfile: остальной код
    работает с XML регулярками и от форматирования не зависит."""
    dest.mkdir(parents=True, exist_ok=True)
    unpack_script = _docx_office_script("unpack.py")
    if unpack_script is not None:
        subprocess.run([sys.executable, str(unpack_script), str(docx_path), str(dest)], check=True)
        return
    import zipfile
    with zipfile.ZipFile(docx_path) as zf:
        zf.extractall(dest)


# --------------------------------------------------------------------------- #
# Чтение styles.xml
# --------------------------------------------------------------------------- #

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_styles(styles_xml: str) -> Dict[str, str]:
    """Возвращает словарь styleId → name."""
    out: Dict[str, str] = {}
    for m in re.finditer(
        r'<w:style[^>]*\bw:styleId="([^"]+)"[^>]*>(.*?)</w:style>',
        styles_xml,
        re.DOTALL,
    ):
        sid = m.group(1)
        body = m.group(2)
        nm = re.search(r'<w:name\s+w:val="([^"]+)"', body)
        if nm:
            out[sid] = nm.group(1)
    return out


def build_style_map(id_to_name: Dict[str, str]) -> Dict[str, Optional[str]]:
    """role -> styleId или None."""
    # name (lower) -> styleId
    name_to_id: Dict[str, str] = {n.lower(): sid for sid, n in id_to_name.items()}
    result: Dict[str, Optional[str]] = {}
    for role, candidates in ROLE_TO_NAMES.items():
        chosen: Optional[str] = None
        for cand in candidates:
            cand_l = cand.lower()
            # сначала ищем точное совпадение, потом по подстроке
            if cand_l in name_to_id:
                chosen = name_to_id[cand_l]
                break
            for full_name, sid in name_to_id.items():
                if cand_l == full_name:
                    chosen = sid
                    break
                if cand_l in full_name and chosen is None:
                    chosen = sid
                    # без break — может встретиться более точное ниже
            if chosen:
                break
        result[role] = chosen
    return result


# --------------------------------------------------------------------------- #
# Анализ document.xml
# --------------------------------------------------------------------------- #

def _extract_text(p_xml: str) -> str:
    """Вытаскивает весь видимый текст из одного <w:p>...</w:p>."""
    parts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", p_xml, re.DOTALL)
    text = "".join(parts)
    # Базовое раскодирование сущностей
    text = (
        text.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&apos;", "'")
    )
    return text.strip()


def iter_paragraphs(doc_xml: str):
    """Yield (offset_start, offset_end, p_xml) для каждого <w:p>."""
    for m in re.finditer(r"<w:p\b[^>]*>(?:(?!<w:p\b).)*?</w:p>", doc_xml, re.DOTALL):
        yield m.start(), m.end(), m.group(0)


def detect_kind(title_text_lower: str) -> str:
    for kind, markers in KIND_MARKERS.items():
        if any(mk in title_text_lower for mk in markers):
            return kind
    return "unknown"


def find_body_start(doc_xml: str, style_map: Dict[str, Optional[str]]) -> int:
    """Находит точку начала тела отчёта (после оглавления / листа замечаний).

    Реализация делегирована модулю insert_into_doc.py, чтобы оба скрипта
    использовали ОДНУ И ТУ ЖЕ логику (включая обработку <w:sdt>-обёртки
    вокруг оглавления и других случаев).
    """
    # Импортируем по месту использования: insert_into_doc находится в той же
    # директории scripts/.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from insert_into_doc import find_body_start as _impl
    return _impl(doc_xml, style_map)


def collect_outline(doc_xml: str, style_map: Dict[str, Optional[str]]) -> List[Dict]:
    """Собирает существующие заголовки по их стилям."""
    role_to_level = {
        "heading_1": 1,
        "heading_2": 2,
        "heading_3": 3,
        "heading_4": 4,
        "structural": 0,
    }
    style_to_level: Dict[str, int] = {}
    for role, level in role_to_level.items():
        sid = style_map.get(role)
        if sid:
            style_to_level[sid] = level

    outline: List[Dict] = []
    for start, end, p in iter_paragraphs(doc_xml):
        m = re.search(r'<w:pStyle\s+w:val="([^"]+)"', p)
        if not m:
            continue
        sid = m.group(1)
        if sid not in style_to_level:
            continue
        text = _extract_text(p)
        if not text:
            continue
        outline.append({
            "level": style_to_level[sid],
            "text": text,
            "style_id": sid,
            "offset": start,
        })
    return outline


def collect_captions(doc_xml: str, style_map: Dict[str, Optional[str]]) -> List[Dict]:
    """Существующие подписи (рисунков/таблиц/листингов)."""
    role_caps = {
        "figure_caption": "figure",
        "table_caption":  "table",
        "listing_caption": "listing",
    }
    style_to_kind: Dict[str, str] = {}
    for role, kind in role_caps.items():
        sid = style_map.get(role)
        if sid:
            style_to_kind[sid] = kind

    captions: List[Dict] = []
    for start, _, p in iter_paragraphs(doc_xml):
        m = re.search(r'<w:pStyle\s+w:val="([^"]+)"', p)
        if not m:
            continue
        sid = m.group(1)
        if sid not in style_to_kind:
            continue
        captions.append({
            "kind": style_to_kind[sid],
            "text": _extract_text(p),
            "offset": start,
        })
    return captions


def extract_title_text(doc_xml: str) -> str:
    """Достаём текст с титульной страницы (всё до первого <w:sectPr>)."""
    sect = re.search(r"<w:sectPr\b", doc_xml)
    head = doc_xml[: sect.start()] if sect else doc_xml[:5000]
    pieces = re.findall(r"<w:t[^>]*>(.*?)</w:t>", head, re.DOTALL)
    return " ".join(pieces)


def find_task_text(doc_xml: str) -> Optional[str]:
    """Пытается найти текст задания (для КР — есть отдельный лист 'ЗАДАНИЕ НА…')."""
    # Эвристика: ищем абзац с большим заглавным словом ЗАДАНИЕ и собираем следующие
    # 20 абзацев или до структурного элемента ОГЛАВЛЕНИЕ.
    p_list = list(iter_paragraphs(doc_xml))
    start_idx = None
    for i, (_, _, p) in enumerate(p_list):
        text = _extract_text(p)
        if re.search(r"\bЗАДАНИЕ\b", text) and len(text) < 120:
            start_idx = i
            break
    if start_idx is None:
        return None
    chunks: List[str] = []
    for j in range(start_idx, min(start_idx + 40, len(p_list))):
        text = _extract_text(p_list[j][2])
        if not text:
            continue
        if "ОГЛАВЛЕНИЕ" in text.upper() or "СОДЕРЖАНИЕ" in text.upper():
            break
        chunks.append(text)
    return "\n".join(chunks) if chunks else None


# --------------------------------------------------------------------------- #
# Главная функция
# --------------------------------------------------------------------------- #

def analyze(docx_path: Path, unpacked_dir: Path) -> Dict:
    unpack_docx(docx_path, unpacked_dir)

    styles_xml_path = unpacked_dir / "word" / "styles.xml"
    doc_xml_path = unpacked_dir / "word" / "document.xml"

    styles_xml = _read(styles_xml_path)
    doc_xml = _read(doc_xml_path)

    id_to_name = parse_styles(styles_xml)
    style_map = build_style_map(id_to_name)

    # Тип работы
    title_text = extract_title_text(doc_xml)
    kind = detect_kind(title_text.lower())

    # Дисциплина — берём строку после "дисциплине"
    discipline = None
    m = re.search(r"дисциплине\s+([А-ЯA-Z][^\n]{2,80})", title_text, re.IGNORECASE)
    if m:
        discipline = m.group(1).strip(" _:.,")

    body_offset = find_body_start(doc_xml, style_map)
    outline = collect_outline(doc_xml, style_map)
    captions = collect_captions(doc_xml, style_map)
    task_text = find_task_text(doc_xml)

    # Список media
    media_dir = unpacked_dir / "word" / "media"
    media_files = sorted([f.name for f in media_dir.iterdir()]) if media_dir.exists() else []

    return {
        "kind": kind,
        "discipline": discipline,
        "title_excerpt": title_text[:400],
        "task_text": task_text,
        "style_map": style_map,
        "id_to_name": id_to_name,
        "existing_outline": [
            {"level": o["level"], "text": o["text"], "style_id": o["style_id"]}
            for o in outline
        ],
        "existing_captions": [
            {"kind": c["kind"], "text": c["text"]} for c in captions
        ],
        "body_start_offset": body_offset,
        "document_length": len(doc_xml),
        "media_files_count": len(media_files),
        "unpacked_dir": str(unpacked_dir),
    }


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: analyze_template.py <template.docx> <unpacked_dir>",
              file=sys.stderr)
        sys.exit(2)
    docx_path = Path(sys.argv[1]).resolve()
    unpacked_dir = Path(sys.argv[2]).resolve()
    if not docx_path.is_file():
        raise SystemExit(f"Файл шаблона не найден: {docx_path}")

    result = analyze(docx_path, unpacked_dir)

    # сохраним style_map и общий анализ рядом с unpacked_dir
    parent = unpacked_dir.parent
    (parent / "style_map.json").write_text(
        json.dumps(result["style_map"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (parent / "analysis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # В stdout — компактная сводка
    summary = {
        "kind": result["kind"],
        "discipline": result["discipline"],
        "style_map": result["style_map"],
        "outline_size": len(result["existing_outline"]),
        "captions_size": len(result["existing_captions"]),
        "body_start_offset": result["body_start_offset"],
        "task_text_found": result["task_text"] is not None,
        "unpacked_dir": result["unpacked_dir"],
        "style_map_path": str(parent / "style_map.json"),
        "analysis_path": str(parent / "analysis.json"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
