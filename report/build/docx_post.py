"""Пост-обработка распакованного документа после insert_into_doc: поле оглавления и settings.xml."""
from pathlib import Path

from lxml import etree

from title import q

# Элементы CT_Settings, перед которыми по схеме должен стоять updateFields.
_AFTER_UPDATE_FIELDS = ["hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids", "mathPr",
                        "attachedSchema", "themeFontLang", "clrSchemeMapping", "doNotIncludeSubdocsInStats",
                        "doNotAutoCompressPictures", "forceUpgrade", "captions", "readModeInkLockDown",
                        "smartTagType", "schemaLibrary", "shapeDefaults", "doNotEmbedSmartTags",
                        "decimalSymbol", "listSeparator"]


def _fld_type(run) -> str | None:
    fc = run.find(q("fldChar"))
    return fc.get(q("fldCharType")) if fc is not None else None


def fix_toc(unpacked: Path, toc_style_ids: set[str]) -> None:
    """Оставляет от поля TOC только begin/instr/separate/end (dirty=true): Word пересоберёт его при открытии.

    insert_into_doc срезает тело вместе с абзацем, где у шаблона стоял fldChar end, поэтому end
    добавляется заново, а закешированные пункты старой работы удаляются.
    """
    path = unpacked / "word" / "document.xml"
    tree = etree.parse(str(path))
    toc_p = next(p for p in tree.iter(q("p"))
                 if any("TOC" in (t.text or "") for t in p.iter(q("instrText"))))
    seen_separate = False
    for child in list(toc_p):
        if child.tag == q("pPr"):
            continue
        if seen_separate:
            toc_p.remove(child)
        elif child.tag == q("r") and _fld_type(child) == "separate":
            seen_separate = True
    if not seen_separate:
        raise SystemExit("у поля TOC нет fldChar separate")
    end = etree.SubElement(toc_p, q("r"))
    etree.SubElement(end, q("fldChar")).set(q("fldCharType"), "end")
    begin = next(r for r in toc_p.iter(q("r")) if _fld_type(r) == "begin")
    begin.find(q("fldChar")).set(q("dirty"), "true")

    nxt = toc_p.getnext()
    while nxt is not None and nxt.tag == q("p"):
        style = nxt.find(f"{q('pPr')}/{q('pStyle')}")
        only_end = [_fld_type(r) for r in nxt.iter(q("r")) if _fld_type(r)] == ["end"]
        if (style is not None and style.get(q("val")) in toc_style_ids) or only_end:
            following = nxt.getnext()
            nxt.getparent().remove(nxt)
            nxt = following
        else:
            break
    tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=True)


def enable_update_fields(unpacked: Path) -> None:
    path = unpacked / "word" / "settings.xml"
    tree = etree.parse(str(path))
    root = tree.getroot()
    if root.find(q("updateFields")) is not None:
        return
    flag = etree.Element(q("updateFields"))
    flag.set(q("val"), "true")
    anchor = next((el for el in root if etree.QName(el).localname in _AFTER_UPDATE_FIELDS), None)
    if anchor is not None:
        anchor.addprevious(flag)
    else:
        root.append(flag)
    tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=True)
