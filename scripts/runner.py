"""
Runner central para aplicar os scripts SQL do projeto contra um banco-alvo.

Uso:
    python -m scripts.runner --target analytics --group schema
    python -m scripts.runner --target analytics --group all
    python -m scripts.runner --target core --group indexes

Cada "group" corresponde a uma pasta em db/ (schema, functions, procedures,
triggers, views, indexes, governance, monitoring). Os arquivos .sql de uma
pasta sao aplicados em ordem alfabetica -- por isso os arquivos sao
prefixados com numero (01_, 02_, ...).
"""

import argparse
import sys
from pathlib import Path

from scripts.db.connection import connect

DB_DIR = Path(__file__).resolve().parent.parent / "db"

GROUP_ORDER = [
    "schema",
    "governance",
    "monitoring",
    "functions",
    "procedures",
    "triggers",
    "views",
    "indexes",
]


def sql_files(group: str) -> list[Path]:
    folder = DB_DIR / group
    if not folder.is_dir():
        raise ValueError(f"grupo invalido: {group!r} (pasta {folder} nao existe)")
    return sorted(folder.glob("*.sql"))


def apply_group(conn, group: str) -> None:
    files = sql_files(group)
    if not files:
        print(f"[{group}] nenhum arquivo .sql encontrado, pulando.")
        return

    with conn.cursor() as cur:
        for path in files:
            print(f"[{group}] aplicando {path.name} ...")
            cur.execute(path.read_text(encoding="utf-8"))
    conn.commit()
    print(f"[{group}] ok ({len(files)} arquivo(s)).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=["core", "auth", "analytics"])
    parser.add_argument("--group", required=True, choices=[*GROUP_ORDER, "all"])
    args = parser.parse_args()

    groups = GROUP_ORDER if args.group == "all" else [args.group]

    conn = connect(args.target)
    try:
        for group in groups:
            try:
                apply_group(conn, group)
            except Exception:
                conn.rollback()
                print(f"[{group}] FALHOU, alteracoes desse grupo revertidas.", file=sys.stderr)
                raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
