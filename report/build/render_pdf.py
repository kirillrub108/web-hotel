"""Визуальная проверка: Word (COM) обновляет поля и экспортирует PDF, PyMuPDF рендерит ключевые страницы в PNG.

Нужны Microsoft Word, pywin32 и pymupdf. Исходный .docx не сохраняется (поля обновляются только для PDF).
    python report/build/render_pdf.py [страницы через запятую]
"""
import sys
from pathlib import Path

import pymupdf
import win32com.client

HERE = Path(__file__).resolve().parent
DOCX = HERE.parent / "Курсовая_работа.docx"
OUT = HERE / "render"


def export_pdf() -> Path:
    OUT.mkdir(exist_ok=True)
    pdf = OUT / "Курсовая_работа.pdf"
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(str(DOCX), ReadOnly=True, AddToRecentFiles=False)
        doc.Fields.Update()
        for toc in doc.TablesOfContents:
            toc.Update()
        doc.ExportAsFixedFormat(str(pdf), 17)  # wdExportFormatPDF
        doc.Close(SaveChanges=0)
    finally:
        word.Quit()
    return pdf


def main() -> None:
    pdf = export_pdf()
    doc = pymupdf.open(pdf)
    marks = {}
    for i, page in enumerate(doc, 1):
        head = [ln.strip() for ln in page.get_text().splitlines() if ln.strip() and not ln.strip().isdigit()][:2]
        for key in ("НОРМАТИВНЫЕ ССЫЛКИ", "ВВЕДЕНИЕ", "1 АНАЛИТИЧЕСКАЯ ЧАСТЬ", "2 ПРОЕКТНАЯ ЧАСТЬ", "ЗАКЛЮЧЕНИЕ",
                    "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", "ПРИЛОЖЕНИЕ А", "Сведения о самостоятельности"):
            if any(ln.startswith(key) for ln in head) and key not in marks:
                marks[key] = i
    print(f"страниц: {len(doc)}; начала разделов: {marks}")
    main_pages = marks.get("ПРИЛОЖЕНИЕ А", len(doc)) - marks.get("НОРМАТИВНЫЕ ССЫЛКИ", 1)
    print(f"основная часть (от нормативных ссылок до приложений): {main_pages} стр.")
    pages = [int(p) for p in sys.argv[1].split(",")] if len(sys.argv) > 1 else [1, 2, 3, 4]
    for n in pages:
        pix = doc[n - 1].get_pixmap(dpi=80)
        pix.save(OUT / f"page_{n:03d}.png")
    print("png:", ", ".join(f"page_{n:03d}.png" for n in pages))


if __name__ == "__main__":
    main()
