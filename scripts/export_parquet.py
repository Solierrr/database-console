"""Stream PostgreSQL tables to Databricks-compatible Parquet files."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import psycopg2
from dotenv import dotenv_values
from psycopg2 import sql


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("core", "auth", "all"))
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--output-root", default="exports")
    parser.add_argument("--fetch-size", type=int, default=10_000)
    args = parser.parse_args()
    if args.fetch_size < 1:
        parser.error("--fetch-size must be greater than zero")
    return args


def choose_target(target: str | None) -> list[str]:
    if target:
        return ["core", "auth"] if target == "all" else [target]

    choices = {"1": "core", "2": "auth", "3": "all"}
    print("Qual banco PostgreSQL exportar para Parquet?")
    print("  1. core\n  2. auth\n  3. todos (core e auth)")
    while True:
        answer = input("Digite 1, 2 ou 3: ").strip()
        if answer in choices:
            selected = choices[answer]
            return ["core", "auth"] if selected == "all" else [selected]
        print("Escolha 1, 2 ou 3.")


def read_environment(env_path: Path) -> tuple[dict[str, str], str]:
    if not env_path.is_file():
        raise FileNotFoundError(
            f"Arquivo {env_path} não encontrado. Execute make extract-env ENV=prod primeiro."
        )

    values = {
        key: value
        for key, value in dotenv_values(env_path).items()
        if value is not None
    }
    header = env_path.read_text(encoding="utf-8-sig").splitlines()[0]
    match = re.search(r"\bEnvironment=(local|qa|prod)\b", header, re.IGNORECASE)
    if not match:
        raise ValueError(
            f"Não consegui identificar o ambiente no cabeçalho de {env_path}. "
            "Extraia o .env novamente com make extract-env ENV=prod."
        )

    required = (
        "DB_POSTGRES_HOST",
        "DB_POSTGRES_PORT",
        "DB_POSTGRES_USER",
        "DB_POSTGRES_PASSWORD",
    )
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise ValueError(f"Variáveis ausentes em {env_path}: {', '.join(missing)}")
    return values, match.group(1).lower()


def arrow_type(column: dict[str, object]) -> pa.DataType:
    data_type = str(column["data_type"]).lower()
    if data_type == "boolean":
        return pa.bool_()
    if data_type == "smallint":
        return pa.int16()
    if data_type == "integer":
        return pa.int32()
    if data_type == "bigint":
        return pa.int64()
    if data_type == "real":
        return pa.float32()
    if data_type == "double precision":
        return pa.float64()
    if data_type == "numeric":
        precision = column["numeric_precision"]
        scale = column["numeric_scale"]
        if precision and 1 <= int(precision) <= 38 and scale is not None:
            precision = int(precision)
            scale = int(scale)
            return pa.decimal128(precision, scale)
        return pa.string()
    if data_type == "date":
        return pa.date32()
    if data_type == "timestamp without time zone":
        return pa.timestamp("us")
    if data_type == "timestamp with time zone":
        return pa.timestamp("us", tz="UTC")
    if data_type == "bytea":
        return pa.binary()
    # Keep UUID, enums, JSON, arrays, and extension types portable to Spark.
    return pa.string()


def convert_value(value: object, column: dict[str, object], target_type: pa.DataType) -> object:
    if value is None:
        return None
    data_type = str(column["data_type"]).lower()
    udt_name = str(column["udt_name"]).lower()
    if pa.types.is_string(target_type):
        if data_type in ("json", "jsonb") or data_type == "array" or isinstance(
            value, (dict, list, tuple)
        ):
            return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
        if udt_name == "uuid" or isinstance(value, (uuid.UUID, Decimal)):
            return str(value)
        return str(value)
    return value


def get_tables(connection: psycopg2.extensions.connection) -> list[tuple[str, str]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name
            """
        )
        return [(schema, table) for schema, table in cursor.fetchall()]


def get_columns(
    connection: psycopg2.extensions.connection, schema: str, table: str
) -> list[dict[str, object]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name, data_type, udt_name, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, table),
        )
        return [
            dict(
                zip(
                    ("name", "data_type", "udt_name", "numeric_precision", "numeric_scale"),
                    row,
                )
            )
            for row in cursor.fetchall()
        ]


def export_table(
    connection: psycopg2.extensions.connection,
    schema: str,
    table: str,
    destination: Path,
    fetch_size: int,
) -> int:
    columns = get_columns(connection, schema, table)
    if not columns:
        return 0
    schema_arrow = pa.schema(
        [pa.field(str(column["name"]), arrow_type(column)) for column in columns]
    )
    query = sql.SQL("SELECT * FROM {}.{}").format(
        sql.Identifier(schema), sql.Identifier(table)
    )
    row_count = 0
    with connection.cursor(name=f"parquet_{uuid.uuid4().hex}") as cursor:
        cursor.itersize = fetch_size
        cursor.execute(query)
        with pq.ParquetWriter(destination, schema_arrow, compression="snappy") as writer:
            while rows := cursor.fetchmany(fetch_size):
                arrays = []
                for index, column in enumerate(columns):
                    arrow_field = schema_arrow.field(index)
                    values = [
                        convert_value(row[index], column, arrow_field.type)
                        for row in rows
                    ]
                    arrays.append(
                        pa.array(values, type=arrow_field.type, from_pandas=True)
                    )
                writer.write_table(
                    pa.Table.from_arrays(arrays, schema=schema_arrow),
                    row_group_size=fetch_size,
                )
                row_count += len(rows)
    return row_count


def export_database(
    service: str,
    values: dict[str, str],
    environment: str,
    output_root: Path,
    fetch_size: int,
) -> Path:
    database_key = f"DB_POSTGRES_{service.upper()}"
    database = values.get(database_key)
    if not database:
        raise ValueError(f"{database_key} não está definido no .env")

    connection_options: dict[str, object] = {
        "host": values["DB_POSTGRES_HOST"],
        "port": int(values["DB_POSTGRES_PORT"]),
        "user": values["DB_POSTGRES_USER"],
        "password": values["DB_POSTGRES_PASSWORD"],
        "dbname": database,
        "connect_timeout": 15,
        "application_name": "database-console-parquet-export",
    }
    if values.get("DB_POSTGRES_SSLMODE"):
        connection_options["sslmode"] = values["DB_POSTGRES_SSLMODE"]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-UTC")
    parent = output_root / environment / service
    parent.mkdir(parents=True, exist_ok=True)
    final_dir = parent / timestamp
    stage_dir = parent / f".{timestamp}.tmp-{uuid.uuid4().hex}"
    stage_dir.mkdir()
    manifest: list[dict[str, object]] = []

    try:
        with psycopg2.connect(**connection_options) as connection:
            tables = get_tables(connection)
            if not tables:
                raise RuntimeError(f"Nenhuma tabela encontrada no banco '{service}'.")
            for schema_name, table_name in tables:
                table_folder = re.sub(
                    r"[^A-Za-z0-9_.-]+", "_", f"{schema_name}__{table_name}"
                )
                table_dir = stage_dir / table_folder
                table_dir.mkdir()
                relative_file = f"{table_folder}/part-00000.parquet"
                print(f"Exportando {schema_name}.{table_name}...", flush=True)
                count = export_table(
                    connection,
                    schema_name,
                    table_name,
                    table_dir / "part-00000.parquet",
                    fetch_size,
                )
                manifest.append(
                    {
                        "schema": schema_name,
                        "table": table_name,
                        "file": relative_file,
                        "rows": count,
                    }
                )

        (stage_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "environment": environment,
                    "database": database,
                    "exported_at_utc": datetime.now(timezone.utc).isoformat(),
                    "format": "parquet",
                    "compression": "snappy",
                    "tables": manifest,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        stage_dir.rename(final_dir)
    except Exception:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise

    total_rows = sum(int(item["rows"]) for item in manifest)
    print(
        f"OK: {len(manifest)} tabelas e {total_rows} registros exportados para {final_dir}"
    )
    return final_dir


def main() -> int:
    args = parse_args()
    try:
        env_path = Path(args.env_file).resolve()
        values, environment = read_environment(env_path)
        services = choose_target(args.target)
        for service in services:
            export_database(
                service,
                values,
                environment,
                Path(args.output_root).resolve(),
                args.fetch_size,
            )
    except (OSError, ValueError, RuntimeError, psycopg2.Error, pa.ArrowException) as exc:
        print(f"Erro na exportação Parquet: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
