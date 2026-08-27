import json
import os
import sys
import uuid
from pathlib import Path

import psycopg2
from databricks import sql as dbsql
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

PG_HOST = os.environ["DB_CORE_HOST"]
PG_PORT = os.environ["DB_CORE_PORT"]
PG_USER = os.environ["DB_CORE_USER"]
PG_PASS = os.environ["DB_CORE_PASS"]
PG_DB = os.environ["DB_CORE_NAME"]

DBX_HOST = os.environ["DATABRICKS_HOST"].replace("https://", "")
DBX_HTTP_PATH = os.environ["DATABRICKS_HTTP_PATH"]
DBX_TOKEN = os.environ["DATABRICKS_TOKEN"]
DBX_CATALOG = os.environ["DATABRICKS_CATALOG"]
DBX_SCHEMA = os.environ["DATABRICKS_SCHEMA"]

PG_TO_SQL_TYPE = {
    "integer": "INT",
    "bigint": "BIGINT",
    "smallint": "SMALLINT",
    "boolean": "BOOLEAN",
    "text": "STRING",
    "character varying": "STRING",
    "character": "STRING",
    "uuid": "STRING",
    "json": "STRING",
    "jsonb": "STRING",
    "date": "DATE",
    "timestamp without time zone": "TIMESTAMP",
    "timestamp with time zone": "TIMESTAMP",
    "double precision": "DOUBLE",
    "real": "FLOAT",
}


def sql_type_for(pg_type: str, precision, scale) -> str:
    if pg_type in ("numeric", "decimal"):
        p = precision or 38
        s = scale or 10
        return f"DECIMAL({p},{s})"
    return PG_TO_SQL_TYPE.get(pg_type, "STRING")


def get_tables(pg_cur) -> list[str]:
    pg_cur.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    return [r[0] for r in pg_cur.fetchall()]


def get_columns(pg_cur, table: str):
    pg_cur.execute(
        """
        SELECT column_name, data_type, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return pg_cur.fetchall()


def _to_dbx_value(v):
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return v


def sync_table(pg_cur, dbx_cur, table: str) -> int:
    columns = get_columns(pg_cur, table)
    col_names = [c[0] for c in columns]
    col_defs = ", ".join(
        f"`{name}` {sql_type_for(pg_type, prec, scale)}"
        for name, pg_type, prec, scale in columns
    )

    full_name = f"`{DBX_CATALOG}`.`{DBX_SCHEMA}`.`{table}`"
    dbx_cur.execute(f"CREATE OR REPLACE TABLE {full_name} ({col_defs})")

    quoted_cols = ", ".join(f'"{c}"' for c in col_names)
    pg_cur.execute(f'SELECT {quoted_cols} FROM public."{table}"')
    rows = pg_cur.fetchall()
    if not rows:
        return 0

    rows = [tuple(_to_dbx_value(v) for v in row) for row in rows]

    placeholders = ", ".join(["?"] * len(col_names))
    col_list = ", ".join(f"`{c}`" for c in col_names)
    insert_sql = f"INSERT INTO {full_name} ({col_list}) VALUES ({placeholders})"

    batch_size = 500
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        dbx_cur.executemany(insert_sql, batch)

    return len(rows)


def main():
    pg_conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASS,
        sslmode="require",
    )
    pg_cur = pg_conn.cursor()

    with dbsql.connect(
        server_hostname=DBX_HOST,
        http_path=DBX_HTTP_PATH,
        access_token=DBX_TOKEN,
    ) as dbx_conn:
        dbx_cur = dbx_conn.cursor()
        dbx_cur.execute(f"CREATE SCHEMA IF NOT EXISTS `{DBX_CATALOG}`.`{DBX_SCHEMA}`")

        tables = get_tables(pg_cur)
        print(f"Sincronizando {len(tables)} tabelas para {DBX_CATALOG}.{DBX_SCHEMA} ...")
        for table in tables:
            try:
                n = sync_table(pg_cur, dbx_cur, table)
                print(f"  ok  {table}: {n} linhas")
            except Exception as exc:
                print(f"  FALHOU {table}: {exc}", file=sys.stderr)

        dbx_cur.close()

    pg_cur.close()
    pg_conn.close()
    print("Sincronizacao concluida.")


if __name__ == "__main__":
    main()
