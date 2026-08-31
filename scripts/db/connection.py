"""Resolucao de conexao Postgres por banco-alvo (core, auth, analytics)."""

import os
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

psycopg2.extras.register_uuid()

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(ENV_PATH)

TARGETS = {
    "core": "DB_CORE",
    "auth": "DB_AUTH",
    "analytics": "DB_ANALYTICS",
}


def connect(target: str):
    if target not in TARGETS:
        raise ValueError(f"target invalido: {target!r}. Use um de {list(TARGETS)}")

    prefix = TARGETS[target]
    return psycopg2.connect(
        host=os.environ[f"{prefix}_HOST"],
        port=os.environ[f"{prefix}_PORT"],
        dbname=os.environ[f"{prefix}_NAME"],
        user=os.environ[f"{prefix}_USER"],
        password=os.environ[f"{prefix}_PASS"],
        sslmode=os.environ.get(f"{prefix}_SSLMODE", "require"),
    )
