import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

psycopg2.extras.register_uuid()
load_dotenv()

TARGETS = ("core", "auth")


def connect(target: str):
    """Conecta em coredb/authdb usando as MESMAS credenciais e a mesma
    convencao de nome de banco do Makefile ($(TARGET)$(SUFIX) -- ver
    ENVIRONMENT/SUFIX no Makefile): prod -> "db", qualquer outro valor -> "dbqa".
    """
    if target not in TARGETS:
        raise ValueError(f"Target not found: {target!r}. Use one of them: {list(TARGETS)}")

    suffix = "db" if os.environ.get("ENVIRONMENT", "").lower() == "prod" else "dbqa"
    return psycopg2.connect(
        host=os.environ["HOST"],
        port=os.environ["PORT"],
        dbname=f"{target}{suffix}",
        user=os.environ["USER"],
        password=os.environ["PASSWORD"],
        sslmode=os.environ.get("SSLMODE", "require"),
    )
