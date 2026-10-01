"""Схема БД из backend/app/models.py (разбор ast, без импорта приложения и без базы).

Типы приводятся к PostgreSQL так, как их создаёт SQLAlchemy 2.0 / Alembic проекта.
"""
import ast
from dataclasses import dataclass, field
from pathlib import Path

MODELS = Path(__file__).resolve().parents[2] / "backend" / "app" / "models.py"


@dataclass
class Column:
    name: str
    pg_type: str
    size: str
    nullable: bool
    pk: bool = False
    unique: bool = False
    fk: str | None = None  # "table.column"


@dataclass
class Table:
    cls: str
    name: str
    columns: list[Column] = field(default_factory=list)


_PY_TYPES = {"int": "integer", "str": "varchar", "bool": "boolean", "date": "date", "datetime": "timestamptz"}


def _annotation(node) -> tuple[str, bool]:
    """Mapped[X] / Mapped[X | None] → (X, nullable)."""
    inner = node.slice
    if isinstance(inner, ast.BinOp):
        return ast.unparse(inner.left), True
    text = ast.unparse(inner).strip("\"'")
    if text.endswith("| None"):
        return text.split("|")[0].strip(), True
    return text, False


def _sa_type(call) -> tuple[str, str] | None:
    if isinstance(call, ast.Name):
        call = ast.Call(func=call, args=[], keywords=[])
    if not isinstance(call, ast.Call):
        return None
    name = ast.unparse(call.func)
    if name == "String":
        return "varchar", str(call.args[0].value)
    if name == "Text":
        return "text", "—"
    if name == "Date":
        return "date", "—"
    if name == "DateTime":
        return "timestamptz", "—"
    if name == "JSON":
        return "json", "—"
    if name == "ARRAY":
        base, size = _sa_type(call.args[0])
        return f"{base}[]", size
    return None


def parse_models(path: Path = MODELS) -> list[Table]:
    tables = []
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if not isinstance(node, ast.ClassDef) or not any(ast.unparse(b) == "Base" for b in node.bases):
            continue
        table = Table(cls=node.name, name="")
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and ast.unparse(stmt.targets[0]) == "__tablename__":
                table.name = stmt.value.value
            if not isinstance(stmt, ast.AnnAssign) or not ast.unparse(stmt.annotation).startswith("Mapped["):
                continue
            py, nullable = _annotation(stmt.annotation)
            call = stmt.value
            if call is not None and ast.unparse(call.func) == "relationship":
                continue
            pg, size = _PY_TYPES.get(py, py), "—"
            kw = {}
            if call is not None:
                for arg in call.args:
                    if ast.unparse(arg).startswith("ForeignKey"):
                        kw["fk"] = arg.args[0].value
                    elif (t := _sa_type(arg)) is not None:
                        pg, size = t
                kw.update({k.arg: k.value for k in call.keywords})
            fk = kw.get("fk")
            col = Column(
                name=stmt.target.id,
                pg_type=pg,
                size=size,
                nullable=nullable,
                pk=isinstance(kw.get("primary_key"), ast.Constant) and kw["primary_key"].value is True,
                unique=isinstance(kw.get("unique"), ast.Constant) and kw["unique"].value is True,
                fk=fk,
            )
            if col.pk:
                col.pg_type = "serial"
            if col.pg_type in ("integer", "serial"):
                col.size = "4 байта"
            elif col.pg_type == "boolean":
                col.size = "1 байт"
            elif col.pg_type == "date":
                col.size = "4 байта"
            elif col.pg_type == "timestamptz":
                col.size = "8 байт"
            table.columns.append(col)
        tables.append(table)
    return tables


if __name__ == "__main__":
    ts = parse_models()
    assert {t.name for t in ts} >= {"rooms", "bookings", "users"}, ts
    b = next(t for t in ts if t.name == "bookings")
    cols = {c.name: c for c in b.columns}
    assert cols["id"].pk and cols["room_id"].fk == "rooms.id" and not cols["room_id"].nullable
    assert cols["comment"].nullable and cols["comment"].pg_type == "text"
    assert cols["reason_codes"].pg_type == "varchar[]" and cols["reason_codes"].size == "32"
    assert cols["guest_name"].size == "120"
    for t in ts:
        print(t.name, [(c.name, c.pg_type, c.size, "NULL" if c.nullable else "NN", "PK" if c.pk else "", "U" if c.unique else "", c.fk or "") for c in t.columns])
