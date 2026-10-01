"""Диаграммы отчёта: IE-модель и схема БД генерируются из models.py, остальные — из исходников
report/assets/diagrams/*.puml|*.dot. Рендер в PNG 150 dpi: PlantUML (java -jar) и Graphviz (dot).

Инструменты ищутся в report/build/tools (см. report/README.md) или берутся из PATH / PLANTUML_JAR.
"""
import os
import shutil
import subprocess
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent
sys.path.insert(0, str(REPORT))

from content.data_model import ENTITIES, ORDER  # noqa: E402
from schema import parse_models  # noqa: E402

DIAGRAMS = REPORT / "assets" / "diagrams"
TOOLS = HERE / "tools"


def _dot_exe() -> str:
    local = sorted(TOOLS.glob("Graphviz-*/bin/dot.exe"))
    found = str(local[-1]) if local else shutil.which("dot")
    if not found:
        raise SystemExit("Graphviz (dot) не найден: см. report/README.md")
    return found


def _plantuml_jar() -> str:
    jar = os.environ.get("PLANTUML_JAR") or str(TOOLS / "plantuml.jar")
    if not Path(jar).exists():
        raise SystemExit("plantuml.jar не найден: см. report/README.md")
    return jar


def _tables():
    by_name = {t.name: t for t in parse_models()}
    return [by_name[n] for n in ORDER]


def ie_logical_puml() -> str:
    """Логическая модель в нотации IE (crow's foot): сущности и атрибуты по-русски."""
    lines = ["@startuml", "!include _style.iuml", "hide circle", "skinparam linetype ortho",
             "skinparam defaultFontSize 12", "skinparam ClassBackgroundColor #FFFFFF",
             "skinparam ClassBorderColor #333333", "skinparam nodesep 40", "skinparam ranksep 50"]
    for t in _tables():
        ent, _, cols = ENTITIES[t.name]
        lines.append(f'entity "{ent}" as {t.name} {{')
        for c in t.columns:
            if c.pk:
                lines.append(f"  * {cols[c.name][0]} <<PK>>")
                lines.append("  --")
        for c in t.columns:
            if c.pk:
                continue
            mark = "*" if not c.nullable else " "
            tags = " <<FK>>" if c.fk else (" <<AK>>" if c.unique else "")
            lines.append(f"  {mark} {cols[c.name][0]}{tags}")
        lines.append("}")
    for t in _tables():
        for c in t.columns:
            if c.fk:
                parent = c.fk.split(".")[0]
                left = "|o" if c.nullable else "||"
                lines.append(f"{parent} {left}--o{{ {t.name}")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


# Колонки схемы слева направо: дочерние таблицы левее родительских, чтобы связи шли в одну сторону.
SCHEMA_COLUMNS = [["booking_events", "service_orders", "housekeeping_tasks"],
                  ["bookings", "services"],
                  ["promos", "sessions", "email_tokens"],
                  ["rooms", "users", "hotels"]]


def db_schema_dot() -> str:
    """Физическая схема: таблицы с именами и типами полей, связи по внешним ключам."""
    out = ['digraph schema {',
           '  graph [rankdir=LR, dpi=150, nodesep=0.12, ranksep=0.45, fontname="Arial", bgcolor="white",'
           ' splines=spline, newrank=true];',
           '  node [shape=plaintext, fontname="Arial", fontsize=10];',
           '  edge [color="#444444", arrowsize=0.7, dir=both, arrowtail=crow, arrowhead=tee];']
    for col in SCHEMA_COLUMNS:
        out.append("  { rank=same; " + "; ".join(col) + "; }")
        out.extend(f"  {a} -> {b} [style=invis];" for a, b in zip(col, col[1:]))
    for t in _tables():
        rows = [f'<TR><TD COLSPAN="2" BGCOLOR="#D9E2F3"><B>{t.name}</B></TD></TR>']
        for c in t.columns:
            key = "PK " if c.pk else ("FK " if c.fk else "")
            typ = c.pg_type + (f"({c.size})" if c.size.isdigit() else "")
            null = "" if c.nullable or c.pk else " NN"
            # Порт PK — у левой ячейки (связь входит слева), порт FK — у правой (связь выходит справа).
            left_port = f' PORT="{c.name}"' if c.pk else ""
            right_port = f' PORT="{c.name}"' if not c.pk else ""
            rows.append(f'<TR><TD{left_port} ALIGN="LEFT">{key}{escape(c.name)}</TD>'
                        f'<TD{right_port} ALIGN="LEFT">{escape(typ)}{null}</TD></TR>')
        out.append(f'  {t.name} [label=<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="2">'
                   + "".join(rows) + "</TABLE>>];")
    for t in _tables():
        for c in t.columns:
            if c.fk:
                parent, pcol = c.fk.split(".")
                out.append(f"  {t.name}:{c.name}:e -> {parent}:{pcol}:w;")
    out.append("}")
    return "\n".join(out) + "\n"


def render_all() -> list[Path]:
    (DIAGRAMS / "02_ie_logical.puml").write_text(ie_logical_puml(), encoding="utf-8")
    (DIAGRAMS / "03_db_schema.dot").write_text(db_schema_dot(), encoding="utf-8")
    dot = _dot_exe()
    env = dict(os.environ, GRAPHVIZ_DOT=dot)
    for src in sorted(DIAGRAMS.glob("*.dot")):
        subprocess.run([dot, "-Tpng", "-Gdpi=150", str(src), "-o", str(src.with_suffix(".png"))], check=True)
    pumls = [str(p) for p in sorted(DIAGRAMS.glob("[0-9]*.puml"))]
    subprocess.run(["java", "-Djava.awt.headless=true", "-jar", _plantuml_jar(), "-charset", "UTF-8",
                    "-tpng", *pumls], check=True, env=env)
    pngs = sorted(DIAGRAMS.glob("[0-9]*.png"))
    expected = {p.stem for p in DIAGRAMS.glob("[0-9]*.puml")} | {p.stem for p in DIAGRAMS.glob("[0-9]*.dot")}
    missing = expected - {p.stem for p in pngs}
    if missing:
        raise SystemExit(f"не отрендерены: {sorted(missing)}")
    return pngs


if __name__ == "__main__":
    for p in render_all():
        print(p.name)
