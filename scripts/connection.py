import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from scripts.databases import DATABASES

psycopg2.extras.register_uuid()
load_dotenv()

TARGETS = {
    "core" : DATABASES.CORE,
    "auth" : DATABASES.AUTH
}

def connect(target: str) -> None:
    if target not in TARGETS:
        raise ValueError(f"Target not found: {target!r}. Use one of them: {list(TARGETS)}")

    prefix: str = TARGETS[target].value
    return psycopg2.connect(
        host=os.environ[f"{prefix}_HOST"],
        port=os.environ[f"{prefix}_PORT"],
        dbname=os.environ[f"{prefix}_NAME"],
        user=os.environ[f"{prefix}_USER"],
        password=os.environ[f"{prefix}_PASS"],
        sslmode=os.environ.get(f"{prefix}_SSLMODE", "require"),
    )
