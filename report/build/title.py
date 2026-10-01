"""Перенос титульного листа и листа задания из шаблона курсовой в распакованный «Шаблон КР».

Всё до абзаца «ОГЛАВЛЕНИЕ» шаблона курсовой заменяет всё до «ОГЛАВЛЕНИЯ» «Шаблона КР».
Стили сопоставляются по имени, нумерация копируется с новыми id, ссылки на колонтитулы
чужого файла убираются: титул и лист задания остаются без номера, счёт страниц сквозной.
"""
import copy
import re
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def q(tag: str) -> str:
    return f"{{{W}}}{tag}"


def text_of(el) -> str:
    return "".join(t.text or "" for t in el.iter(q("t")))


def _style_names(styles_root) -> dict[str, str]:
    return {s.get(q("styleId")): s.find(q("name")).get(q("val")) for s in styles_root.iter(q("style"))}


def _children_before_toc(body) -> list:
    out = []
    for el in body:
        if el.tag == q("p") and text_of(el).strip().upper() == "ОГЛАВЛЕНИЕ":
            return out
        out.append(el)
    raise SystemExit("абзац «ОГЛАВЛЕНИЕ» не найден")


def _map_styles(frag: list, src_names: dict, dst_ids_by_name: dict) -> None:
    for el in frag:
        for tag in ("pStyle", "rStyle", "tblStyle"):
            for st in list(el.iter(q(tag))):
                name = src_names.get(st.get(q("val")))
                dst = dst_ids_by_name.get(name)
                if dst:
                    st.set(q("val"), dst)
                else:
                    st.getparent().remove(st)


# Элементы pPr, которые по схеме стоят после w:spacing.
_AFTER_SPACING = {"ind", "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc", "textDirection",
                  "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr", "pPrChange"}


def _pin_spacing(frag: list, src_styles_root) -> None:
    """Интервалы абзацев из стилей шаблона курсовой записываются прямым форматированием.

    Normal «Шаблона КР» добавляет 12 pt после абзаца, Normal шаблона курсовой — нет; без этого
    ячейки таблиц титула и листа задания растут, и лист задания не помещается на страницу.
    """
    styles = {s.get(q("styleId")): s for s in src_styles_root.iter(q("style"))}
    default_id = next(s.get(q("styleId")) for s in styles.values()
                      if s.get(q("type")) == "paragraph" and s.get(q("default")) == "1")
    defaults = src_styles_root.find(f"{q('docDefaults')}/{q('pPrDefault')}/{q('pPr')}/{q('spacing')}")

    def chain_spacing(sid: str) -> dict:
        chain = []
        while sid in styles:
            chain.append(styles[sid])
            based = styles[sid].find(q("basedOn"))
            sid = based.get(q("val")) if based is not None else None
        eff = dict(defaults.attrib) if defaults is not None else {}
        for st in reversed(chain):
            sp = st.find(f"{q('pPr')}/{q('spacing')}")
            if sp is not None:
                eff.update(sp.attrib)
        return eff

    for el in frag:
        for p in el.iter(q("p")):
            ppr = p.find(q("pPr"))
            if ppr is None:
                ppr = etree.Element(q("pPr"))
                p.insert(0, ppr)
            st = ppr.find(q("pStyle"))
            eff = chain_spacing(st.get(q("val")) if st is not None else default_id)
            eff.setdefault(q("before"), "0")
            eff.setdefault(q("after"), "0")
            sp = ppr.find(q("spacing"))
            if sp is None:
                sp = etree.Element(q("spacing"))
                anchor = next((c for c in ppr if etree.QName(c).localname in _AFTER_SPACING), None)
                if anchor is not None:
                    anchor.addprevious(sp)
                else:
                    ppr.append(sp)
            for k, v in eff.items():
                if sp.get(k) is None:
                    sp.set(k, v)


def _copy_numbering(frag: list, src_num_root, dst_num_root) -> None:
    """Каждый numId фрагмента получает копию своего abstractNum в numbering.xml «Шаблона КР»."""
    used = {n.get(q("val")) for el in frag for n in el.iter(q("numId"))} - {"0"}
    abstracts = dst_num_root.findall(q("abstractNum"))
    next_abs = max(int(a.get(q("abstractNumId"))) for a in abstracts) + 1
    next_num = max(int(n.get(q("numId"))) for n in dst_num_root.findall(q("num"))) + 1
    remap = {}
    for old in sorted(used):
        src_num = next(n for n in src_num_root.findall(q("num")) if n.get(q("numId")) == old)
        abs_id = src_num.find(q("abstractNumId")).get(q("val"))
        src_abs = next(a for a in src_num_root.findall(q("abstractNum")) if a.get(q("abstractNumId")) == abs_id)
        new_abs = copy.deepcopy(src_abs)
        new_abs.set(q("abstractNumId"), str(next_abs))
        nsid = new_abs.find(q("nsid"))
        if nsid is not None:
            nsid.set(q("val"), f"{0x5EC0DE00 + next_abs:08X}")
        abstracts[-1].addnext(new_abs)
        abstracts.append(new_abs)
        # num — сразу за последним существующим: после него по схеме может стоять только numIdMacAtCleanup.
        num = etree.Element(q("num"))
        dst_num_root.findall(q("num"))[-1].addnext(num)
        num.set(q("numId"), str(next_num))
        etree.SubElement(num, q("abstractNumId")).set(q("val"), str(next_abs))
        remap[old] = str(next_num)
        next_abs += 1
        next_num += 1
    for el in frag:
        for n in el.iter(q("numId")):
            if n.get(q("val")) in remap:
                n.set(q("val"), remap[n.get(q("val"))])


def _drop_foreign_refs(frag: list) -> None:
    for el in frag:
        for tag in ("headerReference", "footerReference"):
            for ref in list(el.iter(q(tag))):
                ref.getparent().remove(ref)
    left = [a for el in frag for e in el.iter() for a in e.attrib if a.startswith(f"{{{R}}}")]
    if left:
        raise SystemExit(f"во фрагменте титула остались r:-ссылки: {left}")


# --- правка текста в run'ах ----------------------------------------------------------------

def _set_run_text(run, value: str) -> None:
    for tab in run.findall(q("tab")):  # поле ФИО в шаблоне — run из одного табулятора
        run.remove(tab)
    ts = run.findall(q("t"))
    if not ts:
        ts = [etree.SubElement(run, q("t"))]
    ts[0].text = value
    if value != value.strip():
        ts[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    for t in ts[1:]:
        run.remove(t)


def _paragraph(root, predicate):
    found = [p for p in root.iter(q("p")) if predicate(text_of(p))]
    if len(found) != 1:
        raise SystemExit(f"ожидался один абзац, найдено {len(found)}")
    return found[0]


def set_tail(p, prefix: str, value: str) -> None:
    """Оставляет run'ы, из которых складывается prefix, следующий run получает value, остальные удаляются."""
    runs = [r for r in p.iter(q("r")) if r.find(q("t")) is not None]
    acc, i = "", 0
    while i < len(runs) and len(acc) < len(prefix):
        acc += text_of(runs[i])
        i += 1
    if acc != prefix:
        raise SystemExit(f"граница run'ов не совпала с префиксом {prefix!r}: {acc!r}")
    if i == len(runs):
        new = copy.deepcopy(runs[-1])
        runs[-1].addnext(new)
        runs.append(new)
    _set_run_text(runs[i], value)
    for r in runs[i + 1:]:
        r.getparent().remove(r)


def put_in_next_cell(root, label: str, value: str) -> None:
    """Пишет value в ячейку, следующую за ячейкой с текстом label (новый run берёт формат абзаца)."""
    cells = [tc for tc in root.iter(q("tc")) if text_of(tc).strip() == label]
    if len(cells) != 1:
        raise SystemExit(f"ячейка {label!r}: найдено {len(cells)}")
    target = cells[0].getnext()
    while target is not None and target.tag != q("tc"):
        target = target.getnext()
    p = target.find(q("p"))
    runs = p.findall(q("r"))
    if runs:
        _set_run_text(runs[0], value)
        for r in runs[1:]:
            p.remove(r)
        return
    run = etree.SubElement(p, q("r"))
    mark = p.find(f"{q('pPr')}/{q('rPr')}")
    if mark is not None:
        run.append(copy.deepcopy(mark))
    _set_run_text(run, value)


def put_in_row_below(root, label: str, value: str) -> None:
    """Пишет value в самую широкую ячейку следующей строки (под строкой «студенту … группы …»)."""
    cell = next(tc for tc in root.iter(q("tc")) if text_of(tc).strip() == label)
    cells = cell.getparent().getnext().findall(q("tc"))
    target = max(cells, key=lambda tc: int(tc.find(f"{q('tcPr')}/{q('tcW')}").get(q("w"))))
    p = target.find(q("p"))
    run = etree.SubElement(p, q("r"))
    mark = p.find(f"{q('pPr')}/{q('rPr')}")
    if mark is not None:
        run.append(copy.deepcopy(mark))
    _set_run_text(run, value)


def put_in_cell_below(root, label: str, value: str) -> None:
    """Пишет value в ячейку того же столбца в следующей строке (строка ФИО под «Выполнил…»)."""
    cell = next(tc for tc in root.iter(q("tc")) if text_of(tc).strip().startswith(label))
    tr = cell.getparent()
    col = tr.findall(q("tc")).index(cell)
    below = tr.getnext().findall(q("tc"))[col]
    run = below.find(f"{q('p')}/{q('r')}")
    _set_run_text(run, value)


def fill(frag_root, s: dict) -> None:
    for r in frag_root.iter(q("r")):
        if text_of(r) == "НАЗВАНИЕ ВАШЕЙ ТЕМЫ":
            _set_run_text(r, s["topic"])
            for color in r.findall(f"{q('rPr')}/{q('color')}"):  # красный цвет — признак плейсхолдера
                color.getparent().remove(color)
    p = _paragraph(frag_root, lambda t: t.startswith("Выполнил (-а)"))
    runs = p.findall(q("r"))
    _set_run_text(runs[0], "Выполнил обучающийся:")
    for r in runs[1:]:
        p.remove(r)
    put_in_cell_below(frag_root, "Выполнил обучающийся:", s["fio"])
    set_tail(_paragraph(frag_root, lambda t: t.startswith("Курс:")), "Курс:", s["course"])
    set_tail(_paragraph(frag_root, lambda t: t.startswith("Группа:")), "Группа:", s["group"])
    # Лист задания
    # Ячейка сразу за «студенту» шириной ~2 см: ФИО пишется в широкую строку под ней.
    put_in_row_below(frag_root, "студенту", s["fio_dative"])
    put_in_next_cell(frag_root, "курса", s["course"])
    set_tail(_paragraph(frag_root, lambda t: t.startswith("группы")), "группы ", s["group"])
    put_in_next_cell(frag_root, "ТЕМА:", s["topic"])


def transfer_title(src_docx: Path, unpacked: Path, student: dict) -> None:
    src = zipfile.ZipFile(src_docx)
    src_body = etree.fromstring(src.read("word/document.xml")).find(q("body"))
    src_styles = etree.fromstring(src.read("word/styles.xml"))
    src_names = _style_names(src_styles)
    src_num = etree.fromstring(src.read("word/numbering.xml"))

    doc_path = unpacked / "word" / "document.xml"
    tree = etree.parse(str(doc_path))
    body = tree.getroot().find(q("body"))
    dst_styles = etree.parse(str(unpacked / "word" / "styles.xml")).getroot()
    dst_ids_by_name = {v: k for k, v in _style_names(dst_styles).items()}
    num_path = unpacked / "word" / "numbering.xml"
    num_tree = etree.parse(str(num_path))

    frag = [copy.deepcopy(e) for e in _children_before_toc(src_body)]
    _pin_spacing(frag, src_styles)
    # Уровень структуры у надписей титула («КУРСОВАЯ РАБОТА», «На тему…») затянул бы их в оглавление.
    for el in frag:
        for lvl in el.iter(q("outlineLvl")):
            lvl.set(q("val"), "9")
    _map_styles(frag, src_names, dst_ids_by_name)
    _copy_numbering(frag, src_num, num_tree.getroot())
    _drop_foreign_refs(frag)

    holder = etree.Element(q("body"))
    holder.extend(frag)
    fill(holder, student)

    for el in _children_before_toc(body):
        body.remove(el)
    for i, el in enumerate(list(holder)):
        body.insert(i, el)

    # Титул теперь отдельный раздел без колонтитулов: «особый первый лист» основного раздела
    # скрыл бы номер на странице ОГЛАВЛЕНИЯ.
    final = body.find(q("sectPr"))
    for tp in final.findall(q("titlePg")):
        final.remove(tp)

    tree.write(str(doc_path), xml_declaration=True, encoding="UTF-8", standalone=True)
    num_tree.write(str(num_path), xml_declaration=True, encoding="UTF-8", standalone=True)
