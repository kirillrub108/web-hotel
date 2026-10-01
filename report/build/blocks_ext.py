"""Расширение BlockFactory скилла unik-report: картинки, листинги в оформлении «Шаблона КР»,
нумерованные списки с перезапуском, таблицы БД, подписи приложений.

Всё, чего нет в style_map, сделано прямым форматированием; новых стилей не создаётся.
Побочные изменения пакета (media, связи, типы содержимого, numbering) копятся и пишутся в flush().
"""
import re
import shutil
import struct
import sys
from pathlib import Path

SKILL_SCRIPTS = Path(__file__).resolve().parents[2] / "unik-report" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from build_blocks import BlockFactory, _ppr, _run  # noqa: E402

EMU_PER_CM = 360000
MAX_WIDTH_CM = 16.5
MAX_HEIGHT_CM = 21.5
SINGLE = '<w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
NO_INDENT = '<w:ind w:left="0" w:firstLine="0"/>'
REL_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


def png_size(path: Path) -> tuple[int, int]:
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"не PNG: {path}")
    return struct.unpack(">II", head[16:24])


class ExtBlockFactory(BlockFactory):
    def __init__(self, style_map: dict, unpacked: Path):
        super().__init__(style_map)
        self.unpacked = unpacked
        doc = (unpacked / "word" / "document.xml").read_text(encoding="utf-8")
        sect = re.findall(r"<w:sectPr\b.*?</w:sectPr>", doc, re.S)[-1]
        pg_w = int(re.search(r'<w:pgSz w:w="(\d+)"', sect).group(1))
        left = int(re.search(r'w:left="(\d+)"', sect).group(1))
        right = int(re.search(r'w:right="(\d+)"', sect).group(1))
        self.text_w = pg_w - left - right
        self._docpr = max([int(x) for x in re.findall(r'<wp:docPr id="(\d+)"', doc)] + [0]) + 1
        rels = (unpacked / "word" / "_rels" / "document.xml.rels").read_text(encoding="utf-8")
        self._rid = max(int(x) for x in re.findall(r'Id="rId(\d+)"', rels)) + 1
        numbering = (unpacked / "word" / "numbering.xml").read_text(encoding="utf-8")
        self._num_id = max(int(x) for x in re.findall(r'<w:num w:numId="(\d+)"', numbering)) + 1
        self._list_abstract = self._find_decimal_paren_abstract(numbering)
        self._media: list[tuple[Path, str, str]] = []  # (src, target name, rId)
        self._nums: list[int] = []

    # ----- служебное -------------------------------------------------------------------- #

    @staticmethod
    def _find_decimal_paren_abstract(numbering: str) -> str:
        """abstractNum шаблона, у которого 1-й уровень — «1)» без привязки к стилю."""
        for m in re.finditer(r'<w:abstractNum [^>]*w:abstractNumId="(\d+)".*?</w:abstractNum>', numbering, re.S):
            lvl0 = re.search(r'<w:lvl w:ilvl="0".*?</w:lvl>', m.group(0), re.S).group(0)
            if 'w:numFmt w:val="decimal"' in lvl0 and 'w:lvlText w:val="%1)"' in lvl0 and "w:pStyle" not in lvl0:
                return m.group(1)
        raise SystemExit("в numbering.xml нет списка вида «1)»")

    def flush(self) -> None:
        word = self.unpacked / "word"
        (word / "media").mkdir(exist_ok=True)
        rels_path = word / "_rels" / "document.xml.rels"
        rels = rels_path.read_text(encoding="utf-8")
        new_rels = "".join(
            f'<Relationship Id="{rid}" Type="{REL_IMAGE}" Target="media/{name}"/>' for _, name, rid in self._media
        )
        rels_path.write_text(rels.replace("</Relationships>", new_rels + "</Relationships>"), encoding="utf-8")
        for src, name, _ in self._media:
            shutil.copyfile(src, word / "media" / name)

        ct_path = self.unpacked / "[Content_Types].xml"
        ct = ct_path.read_text(encoding="utf-8")
        if 'Extension="png"' not in ct:
            ct = ct.replace("<Default ", '<Default Extension="png" ContentType="image/png"/><Default ', 1)
            ct_path.write_text(ct, encoding="utf-8")

        num_path = word / "numbering.xml"
        numbering = num_path.read_text(encoding="utf-8")
        nums = "".join(
            f'<w:num w:numId="{n}"><w:abstractNumId w:val="{self._list_abstract}"/>'
            '<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'
            for n in self._nums
        )
        last = numbering.rindex("</w:num>") + len("</w:num>")  # после num по схеме — только numIdMacAtCleanup
        num_path.write_text(numbering[:last] + nums + numbering[last:], encoding="utf-8")
        self._media, self._nums = [], []

    # ----- структурные элементы ----------------------------------------------------------- #

    def structural(self, text: str, *, in_toc: bool = True) -> str:
        """Как в скилле, плюс outlineLvl 0: иначе поле TOC \\u не включит элемент в оглавление."""
        ppr = _ppr(style_id=self.s["structural"], page_break_before=True, outline_lvl=0 if in_toc else None)
        return f"<w:p>{ppr}{_run(text)}</w:p>"

    def centered(self, text: str, *, bold: bool = False) -> str:
        rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
        ppr = _ppr(style_id=self.s["body"], keep_next=True, indent=NO_INDENT, jc="center")
        return f"<w:p>{ppr}{_run(text, rpr)}</w:p>"

    # ----- рисунок ------------------------------------------------------------------------ #

    def figure_image(self, png_path: Path, width_cm: float = MAX_WIDTH_CM, crop_ratio: float | None = None,
                     max_height_cm: float = MAX_HEIGHT_CM) -> str:
        """Рисунок по ширине области текста. crop_ratio — показать только верх картинки высотой
        width × crop_ratio (обрезка a:srcRect, файл не меняется): для длинных снимков страниц."""
        png_path = Path(png_path)
        w_px, h_px = png_size(png_path)
        src_rect = ""
        if crop_ratio and h_px > w_px * crop_ratio:
            bottom = 1 - w_px * crop_ratio / h_px
            src_rect = f'<a:srcRect b="{round(bottom * 100000)}"/>'
            h_px = round(w_px * crop_ratio)
        width_cm = min(width_cm, MAX_WIDTH_CM)
        height_cm = width_cm * h_px / w_px
        if height_cm > max_height_cm:
            height_cm = max_height_cm
            width_cm = height_cm * w_px / h_px
        cx, cy = int(width_cm * EMU_PER_CM), int(height_cm * EMU_PER_CM)
        rid = f"rId{self._rid}"
        self._rid += 1
        doc_id = self._docpr
        self._docpr += 1
        name = f"report_{doc_id}_{png_path.name}"
        self._media.append((png_path, name, rid))
        drawing = (
            '<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
            f'<wp:docPr id="{doc_id}" name="Рисунок {doc_id}"/>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>'
            "</wp:cNvGraphicFramePr>"
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:nvPicPr><pic:cNvPr id="{doc_id}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/>{src_rect}<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            "</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing>"
        )
        # Одинарный интервал: при полуторном Word добавляет над картинкой пустое место.
        ppr = _ppr(
            style_id=self.s["figure_body"],
            keep_next=True,
            spacing='<w:spacing w:before="120" w:after="0" w:line="240" w:lineRule="auto"/>',
            indent=NO_INDENT,
            jc="center",
        )
        return f"<w:p>{ppr}<w:r>{drawing}</w:r></w:p>"

    # ----- листинги ----------------------------------------------------------------------- #

    def listing(self, caption: str, code: str, *, language: str = "") -> str:
        """b.listing() скилла, доведённый до «Шаблона КР»: рамка CCCCCC, Courier New 10 pt,
        одинарный интервал, без отступа, ширина = область текста; длинный листинг переносится."""
        code = code.replace("\t", "    ")
        code = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", code)
        xml = super().listing(caption, code, language=language)
        cap = self.listing_caption(caption)
        assert xml.startswith(cap)
        tbl = xml[len(cap):]
        sid = self.s["listing_body"]
        tbl = tbl.replace('w:color="000000"', 'w:color="CCCCCC"')
        tbl = tbl.replace("<w:trPr><w:cantSplit/></w:trPr>", "")
        tbl = tbl.replace('w:w="9300"', f'w:w="{self.text_w}"')
        tbl = tbl.replace(_ppr(style_id=sid), _ppr(style_id=sid, spacing=SINGLE, indent=NO_INDENT, jc="left"))
        rpr = '<w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>'
        tbl = tbl.replace("<w:r><w:t", f"<w:r>{rpr}<w:t")
        return cap + tbl

    def appendix_listing(self, label: str, caption: str, code: str) -> str:
        """Листинг приложения: автонумерация подписи выключена (numId 0), номер «А.1» пишется руками."""
        xml = self.listing(caption, code)
        cap = self.listing_caption(caption)
        manual = _ppr(
            style_id=self.s["listing_caption"],
            keep_next=True,
            extra_after_pStyle='<w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr>',
        )
        return f"<w:p>{manual}{_run(f'Листинг {label} — {caption}')}</w:p>" + xml[len(cap):]

    # ----- списки ------------------------------------------------------------------------- #

    def numbered_list(self, items) -> str:
        """Стиль numbered_list шаблона, но свой экземпляр нумерации «1)» — каждый список с единицы."""
        num_id = self._num_id
        self._num_id += 1
        self._nums.append(num_id)
        ppr = _ppr(
            style_id=self.s["numbered_list"],
            extra_after_pStyle=f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num_id}"/></w:numPr>',
            indent='<w:ind w:left="0" w:firstLine="709"/>',
            jc="both",
        )
        return "".join(f"<w:p>{ppr}{_run(it)}</w:p>" for it in items)

    # ----- таблицы ------------------------------------------------------------------------ #

    def auto_widths(self, headers: list[str], rows: list[list[str]]) -> list[int]:
        """Автоподбор ширин столбцов (dxa) по содержимому 12 pt: столбец не уже самого длинного слова,
        остаток ширины делится пропорционально тому, сколько столбцу не хватает до записи в одну строку."""
        pad = 180  # поля ячейки, dxa

        def width(text: str, bold: bool = False) -> float:
            # Средняя ширина символа Times New Roman 12 pt: кириллица ~125 dxa, латиница и цифры ~105;
            # полужирная кириллица шапки — в полтора раза шире.
            w = sum(125 if "а" <= ch.lower() <= "я" or ch in "ёЁ" else 105 for ch in text)
            return w * (1.5 if bold else 1)

        cols = list(zip(headers, *rows))
        breaks = re.compile(r"[\u00ad\u200b\s]+")  # мягкий перенос, разрешённый разрыв, пробел
        minimum = [max([width(w, True) for w in breaks.split(col[0])]
                       + [width(w) for c in col[1:] for w in breaks.split(str(c))]) + pad for col in cols]
        ideal = [max(width(str(c).replace("\u00ad", "").replace("\u200b", "")) for c in col[1:]) + pad
                 for col in cols]
        ideal = [max(i, m) for i, m in zip(ideal, minimum)]
        spare = self.text_w - sum(minimum)
        if spare <= 0:
            return [round(m * self.text_w / sum(minimum)) for m in minimum]
        need = [i - m for i, m in zip(ideal, minimum)]
        if sum(need) <= spare:
            leftover = self.text_w - sum(ideal)
            return [round(i + leftover * i / sum(ideal)) for i in ideal]
        return [round(m + spare * n / sum(need)) for m, n in zip(minimum, need)]

    def data_table(self, caption: str, headers: list[str], rows: list[list[str]], *,
                   merge_cols: tuple[int, ...] = ()) -> str:
        """Таблица 12 pt с автоподбором ширин, повтором шапки на каждой странице и
        вертикальным объединением одинаковых подряд значений в столбцах merge_cols.
        Символ \\u00ad в заголовке — место мягкого переноса."""
        n = len(headers)
        grid = self.auto_widths(headers, rows)
        border = "".join(
            f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            for s in ("top", "left", "bottom", "right", "insideH", "insideV")
        )
        rpr_cell = '<w:rPr><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>'
        rpr_head = '<w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>'

        def cell(text: str, width: int, *, head: bool, vmerge: str | None, jc: str) -> str:
            vm = f'<w:vMerge w:val="{vmerge}"/>' if vmerge == "restart" else ("<w:vMerge/>" if vmerge else "")
            sid = self.s["table_header"] if head else self.s["body"]
            ppr = _ppr(style_id=sid, spacing=SINGLE, indent=NO_INDENT, jc=jc)
            rpr = rpr_head if head else rpr_cell
            body = (f"<w:r>{rpr}<w:softHyphen/></w:r>".join(_run(part, rpr) for part in text.split("\u00ad"))
                    if text and vmerge != "continue" else "")
            return (f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{vm}</w:tcPr>'
                    f"<w:p>{ppr}{body}</w:p></w:tc>")

        out = ['<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>'
               + "".join(cell(h, grid[i], head=True, vmerge=None, jc="center") for i, h in enumerate(headers))
               + "</w:tr>"]
        prev = [None] * n
        for row in rows:
            cells = []
            for i, v in enumerate(row):
                v = str(v)
                vmerge = None
                if i in merge_cols:
                    same = prev[i] == v and all(prev[j] == row[j] for j in merge_cols if j < i)
                    vmerge = "continue" if same else "restart"
                cells.append(cell(v, grid[i], head=False, vmerge=vmerge, jc="left"))
            prev = [str(v) for v in row]
            out.append("<w:tr><w:trPr><w:cantSplit/></w:trPr>" + "".join(cells) + "</w:tr>")

        tbl = (
            "<w:tbl><w:tblPr>"
            f'<w:tblW w:w="{sum(grid)}" w:type="dxa"/><w:jc w:val="center"/>'
            f"<w:tblBorders>{border}</w:tblBorders>"
            '<w:tblLayout w:type="fixed"/>'
            '<w:tblCellMar><w:left w:w="85" w:type="dxa"/><w:right w:w="85" w:type="dxa"/></w:tblCellMar>'
            '<w:tblLook w:val="04A0"/></w:tblPr>'
            "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in grid) + "</w:tblGrid>"
            + "".join(out) + "</w:tbl>"
            '<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="40" w:lineRule="exact"/>'
            '<w:ind w:firstLine="0"/></w:pPr><w:r><w:rPr><w:sz w:val="4"/></w:rPr></w:r></w:p>'
        )
        return self.table_caption(caption) + tbl
