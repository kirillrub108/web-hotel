#!/usr/bin/env python3
"""
build_blocks.py — фабрика XML-блоков для скилла unik-report.

Каждая функция возвращает XML-строку, готовую к вставке в <w:body>
шаблона САФУ. Все блоки опираются на стили шаблона (style_map),
а не на хард-кодированные styleId, поэтому работают и в КР, и в ЛП.

Использование:
    from build_blocks import BlockFactory, load_style_map

    smap = load_style_map('/path/to/style_map.json')
    b = BlockFactory(smap)

    chunks = [
        b.structural('ВВЕДЕНИЕ'),
        b.paragraph('Цель работы — изучить ...'),
        b.heading(1, 'Теоретическая часть'),
        b.formula('χ² = Σ(mᵢ − m\\'ᵢ)²/m\\'ᵢ', number=1),
        b.figure_placeholder('Гистограмма распределения', height_cm=8),
        b.figure_caption('Гистограмма распределения частот'),
        b.listing(language='python', code='import numpy as np\\n...'),
        b.listing_caption('Расчёт критерия согласия'),
        b.table(headers=['x', 'w'], rows=[['1.2', '0.04']]),
        b.table_caption('Сводка частот'),
    ]
    xml = ''.join(chunks)
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional


# --------------------------------------------------------------------------- #
# Загрузка карты стилей
# --------------------------------------------------------------------------- #

def load_style_map(path: str | Path) -> Dict[str, Optional[str]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Утилиты экранирования
# --------------------------------------------------------------------------- #

def _xml_escape(text: str) -> str:
    """Экранирует под XML и сохраняет ведущие/завершающие пробелы маркером."""
    return html.escape(text, quote=False)


def _needs_preserve(text: str) -> bool:
    return text != text.strip() if text else False


def _t(text: str) -> str:
    """<w:t> с автоматическим xml:space=preserve при необходимости."""
    esc = _xml_escape(text)
    if _needs_preserve(text):
        return f'<w:t xml:space="preserve">{esc}</w:t>'
    return f"<w:t>{esc}</w:t>"


def _run(text: str, rpr: str = "") -> str:
    """Один <w:r> с опциональным <w:rPr>."""
    inner = (rpr or "") + _t(text)
    return f"<w:r>{inner}</w:r>"


def _ppr(
    *,
    style_id: Optional[str] = None,
    keep_next: bool = False,
    page_break_before: bool = False,
    tabs: Optional[str] = None,
    spacing: Optional[str] = None,
    indent: Optional[str] = None,
    contextual_spacing: bool = False,
    jc: Optional[str] = None,
    outline_lvl: Optional[int] = None,
    rpr: Optional[str] = None,
    extra_after_pStyle: str = "",  # совместимость со старым кодом
) -> str:
    """Собирает <w:pPr> с правильным порядком дочерних элементов по схеме
    OOXML CT_PPrBase. Нарушение порядка ломает валидацию.

    Правильный порядок наших элементов:
        pStyle → keepNext → pageBreakBefore → numPr → tabs → spacing → ind →
        → contextualSpacing → jc → outlineLvl → rPr
    """
    parts: List[str] = []
    if style_id:
        parts.append(f'<w:pStyle w:val="{style_id}"/>')
    # extra_after_pStyle оставлен для совместимости — он добавляется как есть.
    # ВНИМАНИЕ: вызывающий должен сам гарантировать правильный порядок
    # внутри extra_after_pStyle. Лучше использовать именованные параметры.
    if keep_next:
        parts.append("<w:keepNext/>")
    if extra_after_pStyle:
        parts.append(extra_after_pStyle)
    if page_break_before:
        parts.append("<w:pageBreakBefore/>")
    if tabs:
        parts.append(tabs)
    if spacing:
        parts.append(spacing)
    if indent:
        parts.append(indent)
    if contextual_spacing:
        parts.append("<w:contextualSpacing/>")
    if jc:
        parts.append(f'<w:jc w:val="{jc}"/>')
    if outline_lvl is not None:
        parts.append(f'<w:outlineLvl w:val="{outline_lvl}"/>')
    if rpr:
        parts.append(rpr)
    if not parts:
        return ""
    return "<w:pPr>" + "".join(parts) + "</w:pPr>"


# --------------------------------------------------------------------------- #
# Главный класс
# --------------------------------------------------------------------------- #

class BlockFactory:
    """Все генераторы блоков для документа-отчёта."""

    def __init__(self, style_map: Dict[str, Optional[str]]):
        self.s = style_map
        self._figure_counter = 0
        self._listing_counter = 0
        self._table_counter = 0
        self._formula_counter = 0

    # ----- базовые блоки --------------------------------------------------- #

    def paragraph(
        self,
        text: str,
        *,
        bold: bool = False,
        italic: bool = False,
        center: bool = False,
        no_indent: bool = False,
    ) -> str:
        """Обычный абзац основного текста."""
        rpr = []
        if bold:   rpr.append("<w:b/>")
        if italic: rpr.append("<w:i/>")
        rpr_str = f"<w:rPr>{''.join(rpr)}</w:rPr>" if rpr else ""

        ppr = _ppr(
            style_id=self.s.get("body"),
            indent='<w:ind w:firstLine="0"/>' if no_indent else None,
            jc="center" if center else None,
        )
        return f"<w:p>{ppr}{_run(text, rpr_str)}</w:p>"

    def rich_paragraph(self, *runs: tuple) -> str:
        """Абзац с разнородными прогонами.

        Каждый run — кортеж (text, **kwargs), где kwargs: bold, italic, code.
        """
        ppr = _ppr(style_id=self.s.get("body"))
        body = []
        for r in runs:
            text, opts = (r if isinstance(r, tuple) else (r, {}))
            opts = opts or {}
            rpr_parts = []
            if opts.get("bold"):   rpr_parts.append("<w:b/>")
            if opts.get("italic"): rpr_parts.append("<w:i/>")
            if opts.get("code"):
                rpr_parts.append(
                    '<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/>'
                )
            rpr_str = f"<w:rPr>{''.join(rpr_parts)}</w:rPr>" if rpr_parts else ""
            body.append(_run(text, rpr_str))
        return f"<w:p>{ppr}{''.join(body)}</w:p>"

    # ----- заголовки ------------------------------------------------------- #

    def heading(self, level: int, text: str) -> str:
        """Заголовок раздела/подраздела (level=1..4).

        Стиль heading_N даёт автонумерацию '1 …', '1.1 …' — поэтому в text
        номера не пишем; пишем только название.

        Заголовок 1-го уровня ВСЕГДА начинается с новой страницы — это
        требование СТО САФУ. Если стиль шаблона уже содержит
        pageBreakBefore, дублирование не повредит (один разрыв всё равно
        будет одним разрывом).
        """
        if level < 1 or level > 4:
            raise ValueError("heading level must be 1..4")
        sid = self.s.get(f"heading_{level}")
        page_break = (level == 1)
        if not sid:
            # fallback: жирный текст + соответствующий outlineLvl
            rpr = "<w:rPr><w:b/></w:rPr>"
            ppr = _ppr(
                page_break_before=page_break,
                spacing='<w:spacing w:before="240" w:after="120"/>',
                indent='<w:ind w:firstLine="0"/>',
                outline_lvl=level - 1,
            )
            return f"<w:p>{ppr}{_run(text, rpr)}</w:p>"
        return f'<w:p>{_ppr(style_id=sid, page_break_before=page_break)}{_run(text)}</w:p>'

    def structural(self, text: str) -> str:
        """Структурный элемент — ОГЛАВЛЕНИЕ, ВВЕДЕНИЕ, ЗАКЛЮЧЕНИЕ и т.п.

        Каждый структурный элемент ВСЕГДА начинается с новой страницы —
        требование СТО САФУ.

        Текст принимаем как есть; стиль обычно содержит caps, так что
        мы не приводим к верхнему регистру здесь, чтобы у тех шаблонов,
        где caps в стиле НЕ задан, заглавность пришла из самого текста.
        """
        sid = self.s.get("structural")
        if not sid:
            ppr = _ppr(
                page_break_before=True,
                spacing='<w:spacing w:before="240" w:after="240"/>',
                indent='<w:ind w:firstLine="0"/>',
                jc="center",
            )
            rpr = '<w:rPr><w:b/><w:caps/></w:rPr>'
            return f"<w:p>{ppr}{_run(text, rpr)}</w:p>"
        return f'<w:p>{_ppr(style_id=sid, page_break_before=True)}{_run(text)}</w:p>'

    # ----- формула --------------------------------------------------------- #

    def formula(self, text: str, *, number: Optional[int] = None) -> str:
        """Формула отдельным абзацем. Если number указан — справа (N) через
        правую табуляцию.
        """
        sid = self.s.get("formula")

        if number is not None:
            ppr = _ppr(
                style_id=sid,
                tabs='<w:tabs><w:tab w:val="right" w:pos="9355"/></w:tabs>',
                indent='<w:ind w:firstLine="0"/>',
                jc="left",
            )
            run_main = _run(text, '<w:rPr><w:i/></w:rPr>')
            tab = "<w:r><w:tab/></w:r>"
            num = _run(f"({number})")
            return f"<w:p>{ppr}{run_main}{tab}{num}</w:p>"

        if sid:
            return f'<w:p>{_ppr(style_id=sid)}{_run(text, "<w:rPr><w:i/></w:rPr>")}</w:p>'
        # fallback
        ppr = _ppr(
            spacing='<w:spacing w:before="120" w:after="120"/>',
            indent='<w:ind w:firstLine="0"/>',
            jc="center",
        )
        return f"<w:p>{ppr}{_run(text, '<w:rPr><w:i/></w:rPr>')}</w:p>"

    # ----- листинг --------------------------------------------------------- #

    def listing(
        self,
        caption: str,
        code: str,
        *,
        language: str = "",
    ) -> str:
        """Листинг кода с подписью и рамкой.

        По СТО САФУ подпись к листингу ставится СВЕРХУ (как у таблицы).
        Сам код заворачивается в таблицу 1×1 с тонкими чёрными границами —
        это визуально выделяет код среди обычного текста и соответствует
        принятой практике оформления листингов в учебных работах САФУ.

        Каждая строка кода — отдельный абзац стиля listing_body внутри
        ячейки. Если стиля нет — fallback на Courier New 11, одинарный
        интервал.

        Метод комбинированный: возвращает «подпись + рамка с кодом».
        Не вызывай ``listing_caption(...)`` отдельно вокруг ``listing(...)``.
        """
        caption_xml = self.listing_caption(caption)

        # Ширина текстового поля A4 при полях 30/20 мм ≈ 9355 dxa.
        # Уменьшим до 9300, чтобы исключить переполнение при padding.
        total_w = 9300

        sid = self.s.get("listing_body")

        # Параграфы со строками кода (каждая строка — свой <w:p>)
        line_paragraphs: List[str] = []
        for line in code.splitlines() or [""]:
            if sid:
                ppr = _ppr(style_id=sid)
                line_paragraphs.append(f"<w:p>{ppr}{_run(line)}</w:p>")
            else:
                # fallback: Courier New 11, без отступа, одинарный интервал
                ppr = _ppr(
                    spacing='<w:spacing w:before="0" w:after="0" '
                            'w:line="240" w:lineRule="auto"/>',
                    indent='<w:ind w:firstLine="0"/>',
                    jc="left",
                )
                rpr = (
                    '<w:rPr>'
                    '<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" '
                    'w:cs="Courier New"/>'
                    '<w:sz w:val="22"/>'
                    '</w:rPr>'
                )
                line_paragraphs.append(f"<w:p>{ppr}{_run(line, rpr)}</w:p>")

        # Внутренние отступы ячейки (margins) — чтобы код не прилипал к рамке.
        cell_margins = (
            "<w:tcMar>"
            '<w:top w:w="80" w:type="dxa"/>'
            '<w:left w:w="120" w:type="dxa"/>'
            '<w:bottom w:w="80" w:type="dxa"/>'
            '<w:right w:w="120" w:type="dxa"/>'
            "</w:tcMar>"
        )
        cell_borders = (
            "<w:tcBorders>"
            '<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '<w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '<w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            "</w:tcBorders>"
        )
        cell = (
            "<w:tc>"
            "<w:tcPr>"
            f'<w:tcW w:w="{total_w}" w:type="dxa"/>'
            f"{cell_borders}"
            f"{cell_margins}"
            "</w:tcPr>"
            f"{''.join(line_paragraphs)}"
            "</w:tc>"
        )
        row = (
            "<w:tr>"
            "<w:trPr><w:cantSplit/></w:trPr>"
            f"{cell}"
            "</w:tr>"
        )
        tbl = (
            "<w:tbl>"
            "<w:tblPr>"
            f'<w:tblW w:w="{total_w}" w:type="dxa"/>'
            '<w:jc w:val="left"/>'
            '<w:tblBorders>'
            '<w:top w:val="single" w:sz="4" w:color="000000"/>'
            '<w:left w:val="single" w:sz="4" w:color="000000"/>'
            '<w:bottom w:val="single" w:sz="4" w:color="000000"/>'
            '<w:right w:val="single" w:sz="4" w:color="000000"/>'
            '</w:tblBorders>'
            '<w:tblLook w:val="04A0"/>'
            "</w:tblPr>"
            "<w:tblGrid>"
            f'<w:gridCol w:w="{total_w}"/>'
            "</w:tblGrid>"
            f"{row}"
            "</w:tbl>"
            # Технически обязательный замыкающий абзац после <w:tbl>,
            # сделан «невидимым» (2 пт, без интервалов).
            '<w:p>'
            '<w:pPr>'
            '<w:spacing w:before="0" w:after="0" w:line="40" w:lineRule="exact"/>'
            '<w:ind w:firstLine="0"/>'
            '</w:pPr>'
            '<w:r><w:rPr><w:sz w:val="4"/></w:rPr></w:r>'
            '</w:p>'
        )
        return caption_xml + tbl

    # ----- подписи --------------------------------------------------------- #

    def figure_caption(self, text: str) -> str:
        """Подпись к рисунку.

        Если стиль figure_caption в шаблоне есть и у него есть автонумерация,
        пишем ТОЛЬКО смысловое название («Гистограмма распределения») —
        префикс «Рисунок N — » добавит Word.

        Если стиля нет — пишем «Рисунок N — текст» руками, ведём собственный
        счётчик.
        """
        sid = self.s.get("figure_caption")
        if sid:
            return f'<w:p>{_ppr(style_id=sid)}{_run(text)}</w:p>'
        self._figure_counter += 1
        ppr = _ppr(
            spacing='<w:spacing w:before="120" w:after="240"/>',
            indent='<w:ind w:firstLine="0"/>',
            jc="center",
        )
        full = f"Рисунок {self._figure_counter} — {text}"
        return f"<w:p>{ppr}{_run(full)}</w:p>"

    def listing_caption(self, text: str) -> str:
        sid = self.s.get("listing_caption")
        if sid:
            return f'<w:p>{_ppr(style_id=sid, keep_next=True)}{_run(text)}</w:p>'
        self._listing_counter += 1
        ppr = _ppr(
            keep_next=True,
            spacing='<w:spacing w:before="240" w:after="120"/>',
            indent='<w:ind w:firstLine="0"/>',
        )
        full = f"Листинг {self._listing_counter} — {text}"
        return f"<w:p>{ppr}{_run(full)}</w:p>"

    def table_caption(self, text: str) -> str:
        sid = self.s.get("table_caption")
        if sid:
            return f'<w:p>{_ppr(style_id=sid, keep_next=True)}{_run(text)}</w:p>'
        self._table_counter += 1
        ppr = _ppr(
            keep_next=True,
            spacing='<w:spacing w:before="240" w:after="120"/>',
            indent='<w:ind w:firstLine="0"/>',
        )
        full = f"Таблица {self._table_counter} — {text}"
        return f"<w:p>{ppr}{_run(full)}</w:p>"

    # ----- рисунок-плейсхолдер --------------------------------------------- #

    def figure_placeholder(
        self,
        description: str,
        *,
        height_cm: float = 7.0,
        width_cm: float = 14.0,
    ) -> str:
        """Заглушка-рамка вместо настоящего рисунка.

        Возвращает таблицу 1x1 заданных размеров с серой рамкой и
        центрированным текстом «[Место для рисунка: <описание>]».

        После этого вызова ОБЯЗАТЕЛЬНО ставится figure_caption(...).
        """
        # 1 см = 567 DXA (twentieths of a point) ≈ 1 см
        width_dxa = int(width_cm * 567)
        height_dxa = int(height_cm * 567)

        # Стиль абзаца внутри ячейки — figure_body, если есть
        fig_sid = self.s.get("figure_body")
        inner_ppr = _ppr(style_id=fig_sid) if fig_sid else _ppr(
            spacing='<w:spacing w:before="0" w:after="0"/>',
            indent='<w:ind w:firstLine="0"/>',
            jc="center",
        )
        run_rpr = (
            '<w:rPr>'
            '<w:i/>'
            '<w:color w:val="808080"/>'
            '<w:sz w:val="22"/>'
            '</w:rPr>'
        )
        text_run = _run(f"[Место для рисунка: {description}]", run_rpr)

        # Рамка вокруг ячейки + фикс. высота
        cell_props = (
            "<w:tcPr>"
            f'<w:tcW w:w="{width_dxa}" w:type="dxa"/>'
            "<w:tcBorders>"
            '<w:top w:val="single" w:sz="4" w:space="0" w:color="A6A6A6"/>'
            '<w:left w:val="single" w:sz="4" w:space="0" w:color="A6A6A6"/>'
            '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="A6A6A6"/>'
            '<w:right w:val="single" w:sz="4" w:space="0" w:color="A6A6A6"/>'
            "</w:tcBorders>"
            '<w:vAlign w:val="center"/>'
            "</w:tcPr>"
        )

        cell = (
            "<w:tc>"
            f"{cell_props}"
            f"<w:p>{inner_ppr}{text_run}</w:p>"
            "</w:tc>"
        )

        row = (
            "<w:tr>"
            "<w:trPr>"
            f'<w:trHeight w:val="{height_dxa}" w:hRule="exact"/>'
            "</w:trPr>"
            f"{cell}"
            "</w:tr>"
        )

        tbl = (
            "<w:tbl>"
            "<w:tblPr>"
            f'<w:tblW w:w="{width_dxa}" w:type="dxa"/>'
            '<w:jc w:val="center"/>'
            "<w:tblLook w:val=\"04A0\"/>"
            "</w:tblPr>"
            "<w:tblGrid>"
            f'<w:gridCol w:w="{width_dxa}"/>'
            "</w:tblGrid>"
            f"{row}"
            "</w:tbl>"
            # Технически обязательный абзац-замыкатель после таблицы.
            # Делаем его «невидимым»: 2 пт, без интервалов, без отступа.
            # Подпись (figure_caption) идёт следующим блоком — её
            # собственного "before"-интервала достаточно.
            '<w:p>'
            '<w:pPr>'
            '<w:spacing w:before="0" w:after="0" w:line="40" w:lineRule="exact"/>'
            '<w:ind w:firstLine="0"/>'
            '</w:pPr>'
            '<w:r><w:rPr><w:sz w:val="4"/></w:rPr></w:r>'
            '</w:p>'
        )
        return tbl

    def table(
        self,
        caption: str,
        *,
        headers: List[str],
        rows: List[List[str]],
        col_widths_dxa: Optional[List[int]] = None,
    ) -> str:
        """Таблица данных с подписью сверху.

        По СТО САФУ подпись к таблице ставится СВЕРХУ (как у листинга).
        Метод комбинированный: сначала ``table_caption(caption)``, затем
        сама таблица. Не вызывай ``table_caption(...)`` отдельно вокруг
        ``table(...)`` — этот метод уже делает это сам.

        Ширина одной колонки по умолчанию ≈ 9000 / N DXA (для книжной A4
        с полями 30/20 мм ширина текста ≈ 9355 DXA, округляем до 9000).
        """
        caption_xml = self.table_caption(caption)

        ncols = len(headers)
        total_w = 9000
        if col_widths_dxa is None:
            col_w = total_w // ncols
            col_widths_dxa = [col_w] * ncols
        else:
            total_w = sum(col_widths_dxa)

        header_sid = self.s.get("table_header")
        body_sid = self.s.get("body")

        def _cell(content: str, width: int, *, header: bool = False) -> str:
            borders = (
                "<w:tcBorders>"
                '<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
                '<w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
                '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
                '<w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
                "</w:tcBorders>"
            )
            tcpr = (
                "<w:tcPr>"
                f'<w:tcW w:w="{width}" w:type="dxa"/>'
                f"{borders}"
                '<w:vAlign w:val="center"/>'
                "</w:tcPr>"
            )
            sid = header_sid if header else body_sid
            ppr = _ppr(
                style_id=sid,
                spacing='<w:spacing w:before="40" w:after="40"/>',
                indent='<w:ind w:firstLine="0"/>',
                jc="center",
            )
            rpr = '<w:rPr><w:b/></w:rPr>' if header else ''
            return f"<w:tc>{tcpr}<w:p>{ppr}{_run(content, rpr)}</w:p></w:tc>"

        def _row(values: List[str], header: bool = False) -> str:
            cells = "".join(
                _cell(str(v), col_widths_dxa[i], header=header)
                for i, v in enumerate(values)
            )
            tr_extra = (
                '<w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>'
                if header else
                '<w:trPr><w:cantSplit/></w:trPr>'
            )
            return f"<w:tr>{tr_extra}{cells}</w:tr>"

        rows_xml = _row(headers, header=True) + "".join(_row(r) for r in rows)
        grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in col_widths_dxa)
        tbl = (
            "<w:tbl>"
            "<w:tblPr>"
            f'<w:tblW w:w="{total_w}" w:type="dxa"/>'
            '<w:jc w:val="center"/>'
            '<w:tblBorders>'
            '<w:top w:val="single" w:sz="4" w:color="000000"/>'
            '<w:left w:val="single" w:sz="4" w:color="000000"/>'
            '<w:bottom w:val="single" w:sz="4" w:color="000000"/>'
            '<w:right w:val="single" w:sz="4" w:color="000000"/>'
            '<w:insideH w:val="single" w:sz="4" w:color="000000"/>'
            '<w:insideV w:val="single" w:sz="4" w:color="000000"/>'
            '</w:tblBorders>'
            '<w:tblLook w:val="04A0"/>'
            "</w:tblPr>"
            f"<w:tblGrid>{grid}</w:tblGrid>"
            f"{rows_xml}"
            "</w:tbl>"
            # Технически обязательный замыкающий абзац после <w:tbl>,
            # сделан «невидимым» (2 пт, без интервалов).
            '<w:p>'
            '<w:pPr>'
            '<w:spacing w:before="0" w:after="0" w:line="40" w:lineRule="exact"/>'
            '<w:ind w:firstLine="0"/>'
            '</w:pPr>'
            '<w:r><w:rPr><w:sz w:val="4"/></w:rPr></w:r>'
            '</w:p>'
        )
        return caption_xml + tbl

    # ----- списки ---------------------------------------------------------- #

    def bullet_list(self, items: Iterable[str]) -> str:
        sid = self.s.get("bullet_list")
        out = []
        for it in items:
            if sid:
                ppr = _ppr(style_id=sid)
                out.append(f"<w:p>{ppr}{_run(it)}</w:p>")
            else:
                # fallback — длинное тире вручную
                ppr = (
                    '<w:pPr>'
                    '<w:ind w:left="568" w:hanging="284" w:firstLine="0"/>'
                    '</w:pPr>'
                )
                out.append(f"<w:p>{ppr}{_run(f'— {it}')}</w:p>")
        return "".join(out)

    def numbered_list(self, items: Iterable[str]) -> str:
        sid = self.s.get("numbered_list")
        items = list(items)
        out = []
        if sid:
            for it in items:
                ppr = _ppr(style_id=sid)
                out.append(f"<w:p>{ppr}{_run(it)}</w:p>")
        else:
            for i, it in enumerate(items, 1):
                ppr = (
                    '<w:pPr>'
                    '<w:ind w:left="568" w:hanging="284" w:firstLine="0"/>'
                    '</w:pPr>'
                )
                out.append(f"<w:p>{ppr}{_run(f'{i}) {it}')}</w:p>")
        return "".join(out)

    def references(self, items: Iterable[str]) -> str:
        """Список использованных источников."""
        sid = self.s.get("references_list")
        items = list(items)
        if sid:
            return "".join(f'<w:p>{_ppr(style_id=sid)}{_run(it)}</w:p>' for it in items)
        # fallback: руками с нумерацией «1. …»
        out = []
        for i, it in enumerate(items, 1):
            ppr = (
                '<w:pPr><w:ind w:left="568" w:hanging="284" w:firstLine="0"/></w:pPr>'
            )
            out.append(f"<w:p>{ppr}{_run(f'{i}. {it}')}</w:p>")
        return "".join(out)

    # ----- разрыв страницы ------------------------------------------------- #

    def page_break(self) -> str:
        return "<w:p><w:r><w:br w:type=\"page\"/></w:r></w:p>"


# --------------------------------------------------------------------------- #
# Самопроверка
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    # Демонстрационный прогон с пустой картой стилей — все fallback'и активны
    b = BlockFactory({})
    parts = [
        b.structural("ВВЕДЕНИЕ"),
        b.paragraph("Цель работы — проверить корректность."),
        b.heading(1, "Теоретическая часть"),
        b.paragraph("Текст параграфа."),
        b.formula("y = a + b·x", number=1),
        b.figure_placeholder("Тестовая диаграмма", height_cm=6),
        b.figure_caption("Тестовый рисунок"),
        b.listing(
            caption="Простая функция",
            code="def f():\n    return 1",
            language="python",
        ),
        b.table(
            caption="Тестовые значения",
            headers=["x", "y"],
            rows=[["1", "2"], ["3", "4"]],
        ),
        b.bullet_list(["первое", "второе"]),
        b.references(["Иванов И.И. Тест. — М., 2024. — 10 с."]),
    ]
    xml = "".join(parts)
    # быстрая проверка: всё должно содержать парные теги
    # Для w:p и w:r считаем только реальные открывающие, исключая w:pPr, w:rPr и т.п.
    import re as _re
    def _count_open(tag: str, s: str) -> int:
        return len(_re.findall(rf"<{tag}(?:\s|>)", s))
    for tag in ("w:p", "w:tbl", "w:r"):
        opens = _count_open(tag, xml)
        closes = xml.count(f"</{tag}>")
        assert opens == closes, f"Несбалансировано {tag}: {opens} open vs {closes} close"
    print("Self-test OK. Total length:", len(xml))
