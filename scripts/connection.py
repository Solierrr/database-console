import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

psycopg2.extras.register_uuid()
load_dotenv()

TARGETS = ("core", "auth")


def connect(target: str):
    """Conecta em coredb/authdb usando as MESMAS credenciais e a mesma
    convencao de nome de banco do Makefile ($(TARGET)db$(SUFIX)): qa usa
    sufixo "qa" (coredbqa/authdbqa, banco compartilhado com prod no mesmo
    host Aiven); local e prod usam o nome puro (coredb/authdb), cada um no
    seu proprio host -- confirmado contra os secrets reais do Infisical.
    """
    if target not in TARGETS:
        raise ValueError(f"Target not found: {target!r}. Use one of them: {list(TARGETS)}")

    suffix = "qa" if os.environ.get("ENVIRONMENT", "").lower() == "qa" else ""
    return psycopg2.connect(
        host=os.environ["HOST"],
        port=os.environ["PORT"],
        dbname=f"{target}db{suffix}",
        user=os.environ["USER"],
        password=os.environ["PASSWORD"],
        sslmode=os.environ.get("SSLMODE", "require"),
    )
