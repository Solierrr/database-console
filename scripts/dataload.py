import csv, json, random, re, string, sys, uuid

from faker import Faker
from datetime import timedelta
from pathlib import Path
from psycopg2.extras import execute_values

from scripts.connection import connect

FAKE = Faker("pt_BR")
Faker.seed(42)
random.seed(42)

CLOUDINARY_DIR = Path(__file__).resolve().parent / "data" / "cloudinary"
CATALOG_DIR = Path(__file__).resolve().parent / "data" / "catalog"
_media_pools: dict[str, list[tuple[str, str]]] = {}
_catalogs: dict[str, list[dict]] = {}


def trunc(value: str, length: int) -> str: return value[:length]
def digits(n: int) -> str: return "".join(random.choices(string.digits, k=n))
def digits_only(value: str) -> str: return re.sub(r"\D", "", value)
def gen_cpf() -> str: return digits_only(FAKE.cpf())
def gen_cnpj() -> str: return digits_only(FAKE.cnpj())
def new_id() -> uuid.UUID: return uuid.uuid4()
def pick(seq):             return random.choice(seq)
def maybe(seq, p=0.7):     return pick(seq) if random.random() < p else None


def unique_username() -> str:
    """Handle publico unico (@user), sempre minusculo -- combina com
    ck_users_username_format em db/core/schema.sql."""
    raw = re.sub(r"[^a-z0-9_]", "_", FAKE.unique.user_name().lower())
    raw = trunc(raw, 30)
    return raw if len(raw) >= 3 else raw.ljust(3, "0")


def media_pool(name: str) -> list[tuple[str, str]]:
    """Le (e cacheia) as linhas de scripts/data/cloudinary/<name>.csv como (url, public_id).
    Pode estar vazio -- cada arquivo cobre um unico campo de imagem e e
    curado manualmente; use pick_media() para ter fallback automatico
    enquanto o CSV nao foi preenchido."""
    if name not in _media_pools:
        path = CLOUDINARY_DIR / f"{name}.csv"
        with open(path, newline="", encoding="utf-8") as fh:
            _media_pools[name] = [(row["url"], row["public_id"]) for row in csv.DictReader(fh)]
    return _media_pools[name]


def pick_media(name: str) -> tuple[str, str]:
    """Escolhe (url, public_id) do pool <name>.csv; se o CSV ainda estiver
    vazio, gera um placeholder via Faker para o dataload continuar rodando."""
    pool = media_pool(name)
    return pick(pool) if pool else (FAKE.image_url(), uuid.uuid4().hex)


def catalog(name: str) -> list[dict]:
    """Le (e cacheia) scripts/data/catalog/<name>.csv como lista de dicts --
    vocabulario fixo (cargos, permissoes, planos etc.) editavel sem tocar
    no codigo."""
    if name not in _catalogs:
        path = CATALOG_DIR / f"{name}.csv"
        with open(path, newline="", encoding="utf-8") as fh:
            _catalogs[name] = list(csv.DictReader(fh))
    return _catalogs[name]


def pick_text(catalog_name: str, column: str) -> str:
    """Escolhe um valor em portugues de scripts/data/catalog/<catalog_name>.csv.
    Usado no lugar de FAKE.text()/FAKE.sentence()/FAKE.bs(), que geram
    lorem ipsum pseudo-latino ou ingles mesmo com o locale pt_BR."""
    return pick(catalog(catalog_name))[column]


class Seeder:
    def __init__(self, scale: float):
        self.conn = None
        self.scale = scale
        self.ids = {}

    def use_connection(self, conn) -> None:
        self.conn = conn

    def n(self, base: int) -> int:
        return max(1, round(base * self.scale))

    def insert(self, table: str, columns: list[str], rows: list[tuple]) -> None:
        if not rows:
            return
        col_list = ", ".join(columns)
        sql = f"INSERT INTO {table} ({col_list}) VALUES %s"
        with self.conn.cursor() as cur:
            execute_values(cur, sql, rows, page_size=500)
        print(f"  {table}: {len(rows)} linha(s)")

    def seed_address(self):
        rows = []
        for _ in range(self.n(150)):
            row_id = new_id()
            rows.append((
                row_id,
                FAKE.estado_sigla(),
                trunc(FAKE.city(), 120),
                trunc(FAKE.bairro(), 120) if hasattr(FAKE, "bairro") else trunc(FAKE.city_suffix(), 120),
                digits(8),
                trunc(FAKE.street_name(), 200),
                str(random.randint(1, 9999)),
            ))
        self.ids.setdefault("address", []).extend(r[0] for r in rows)
        self.insert("address", ["id", "state", "city", "neighborhood", "zip_code", "street", "number"], rows)

    def seed_contact(self):
        rows = []
        for _ in range(self.n(150)):
            row_id = new_id()
            rows.append((row_id, trunc(FAKE.email(), 100), digits(11)))
        self.ids.setdefault("contact", []).extend(r[0] for r in rows)
        self.insert("contact", ["id", "email", "phone"], rows)

    def seed_geolocalization(self):
        rows = []
        for _ in range(self.n(80)):
            row_id = new_id()
            rows.append((
                row_id,
                maybe(self.ids["address"]),
                FAKE.pydecimal(left_digits=3, right_digits=7, positive=False),
                FAKE.pydecimal(left_digits=3, right_digits=7, positive=False),
            ))
        self.insert("geolocalization", ["id", "fk_address", "latitude", "longitude"], rows)

    def seed_auth_user(self):
        rows = []
        for _ in range(self.n(300)):
            row_id = new_id()
            rows.append((
                row_id,
                FAKE.unique.email(),
                maybe([FAKE.date_time_between("-2y", "now")]),
                pick(["ACTIVE", "ACTIVE", "ACTIVE", "LOCKED", "DISABLED"]),
                random.randint(0, 3),
                None,
                maybe([FAKE.date_time_between("-30d", "now")]),
                FAKE.date_time_between("-2y", "-1y"),
                FAKE.date_time_between("-1y", "now"),
            ))
        self.ids.setdefault("auth_user", []).extend(r[0] for r in rows)
        self.insert("auth_user", [
            "id", "primary_email", "email_verified_at", "status", "failed_login_attempts",
            "locked_until", "last_login_at", "created_at", "updated_at",
        ], rows)

    def seed_local_credential(self):
        rows = []
        for auth_id in self.ids["auth_user"]:
            rows.append((
                auth_id,
                FAKE.sha256(),
                FAKE.date_time_between("-1y", "now"),
                random.random() < 0.05,
                FAKE.date_time_between("-2y", "-1y"),
                FAKE.date_time_between("-1y", "now"),
            ))
        self.insert("local_credential", [
            "user_id", "password_hash", "password_changed_at", "must_change", "created_at", "updated_at",
        ], rows)

    def seed_federated_identity(self):
        rows = []
        sample_size = min(len(self.ids["auth_user"]), self.n(50))
        for user_id in random.sample(self.ids["auth_user"], k=sample_size):
            row_id = new_id()
            rows.append((
                row_id,
                user_id,
                "FIREBASE",
                "https://securetoken.google.com/solaria",
                uuid.uuid4().hex,
                FAKE.email(),
                random.random() < 0.8,
                FAKE.date_time_between("-1y", "now"),
                maybe([FAKE.date_time_between("-30d", "now")]),
            ))
        self.insert("federated_identity", [
            "id", "user_id", "authority", "issuer", "subject", "email", "email_verified",
            "created_at", "last_login_at",
        ], rows)

    def seed_one_time_token(self):
        rows = []
        for _ in range(self.n(60)):
            row_id = new_id()
            created = FAKE.date_time_between("-90d", "now")
            rows.append((
                row_id,
                pick(self.ids["auth_user"]),
                FAKE.sha256().encode(),
                pick(["EMAIL_VERIFICATION", "PASSWORD_RESET", "ACCOUNT_LINK"]),
                created + timedelta(hours=1),
                maybe([created + timedelta(minutes=10)], p=0.4),
                created,
            ))
        self.insert("one_time_token", [
            "id", "user_id", "token_hash", "type", "expires_at", "consumed_at", "created_at",
        ], rows)

    def seed_auth_session(self):
        rows = []
        for _ in range(self.n(400)):
            row_id = new_id()
            created = FAKE.date_time_between("-180d", "now")
            revoked = random.random() < 0.2
            methods = random.sample(["PASSWORD", "TOTP", "FEDERATED_FIREBASE"], k=random.randint(1, 2))
            rows.append((
                row_id,
                pick(self.ids["auth_user"]),
                FAKE.ipv4(),
                trunc(FAKE.user_agent(), 500),
                pick(["web", "android", "ios"]),
                methods,
                maybe([created], p=0.3),
                created,
                created + timedelta(days=random.randint(0, 30)),
                created + timedelta(days=30),
                created + timedelta(days=random.randint(1, 29)) if revoked else None,
                pick(["logout", "expired", "security"]) if revoked else None,
            ))
        self.ids.setdefault("auth_session", []).extend(r[0] for r in rows)
        self.insert("auth_session", [
            "id", "user_id", "ip_address", "user_agent", "device", "authentication_methods",
            "mfa_completed_at", "created_at", "last_access_at", "expires_at", "revoked_at", "revocation_reason",
        ], rows)

    def seed_refresh_token(self):
        chain_ids = []
        rows = []
        for session_id in self.ids["auth_session"]:
            previous_id = None
            for _ in range(random.randint(1, 3)):
                row_id = new_id()
                created = FAKE.date_time_between("-30d", "now")
                rows.append((
                    row_id, session_id, FAKE.sha256().encode(),
                    maybe([created + timedelta(minutes=5)], p=0.3), None, None,
                    created + timedelta(days=7), created,
                ))
                if previous_id is not None:
                    chain_ids.append((previous_id, row_id))
                previous_id = row_id
        self.insert("refresh_token", [
            "id", "session_id", "token_hash", "consumed_at", "revoked_at", "replaced_by_id",
            "expires_at", "created_at",
        ], rows)
        if chain_ids:
            with self.conn.cursor() as cur:
                execute_values(
                    cur,
                    "UPDATE refresh_token AS rt SET replaced_by_id = data.next_id "
                    "FROM (VALUES %s) AS data (prev_id, next_id) WHERE rt.id = data.prev_id",
                    chain_ids,
                )
            print(f"  refresh_token: {len(chain_ids)} elo(s) de rotacao encadeados")

    def seed_totp_factor(self):
        rows = []
        for auth_id in random.sample(self.ids["auth_user"], k=self.n(50)):
            row_id = new_id()
            rows.append((
                row_id, auth_id, FAKE.sha256().encode()[:32], FAKE.sha256().encode()[:12],
                "key-" + uuid.uuid4().hex[:8], pick(["SHA1", "SHA256", "SHA512"]), 6, 30,
                maybe([FAKE.date_time_between("-1y", "now")]), maybe([random.randint(1, 999)]),
                FAKE.date_time_between("-1y", "-6M"), FAKE.date_time_between("-6M", "now"),
            ))
        self.insert("totp_factor", [
            "id", "user_id", "secret_ciphertext", "secret_nonce", "encryption_key_id", "algorithm",
            "digits", "period_seconds", "enabled_at", "last_used_counter", "created_at", "updated_at",
        ], rows)

    def seed_security_event(self):
        event_types = [
            "USER_REGISTERED", "LOGIN_SUCCEEDED", "LOGIN_FAILED", "LOGOUT", "PASSWORD_CHANGED",
            "MFA_ENABLED", "SESSION_REVOKED",
        ]
        rows = []
        for _ in range(self.n(300)):
            row_id = new_id()
            rows.append((
                row_id,
                maybe(self.ids["auth_user"], p=0.9),
                maybe(self.ids["auth_session"], p=0.6),
                pick(event_types),
                random.random() < 0.85,
                FAKE.ipv4(),
                trunc(FAKE.user_agent(), 500),
                json.dumps({"note": pick_text("security_event_note", "note")}),
                FAKE.date_time_between("-180d", "now"),
            ))
        self.insert("security_event", [
            "id", "user_id", "session_id", "event_type", "succeeded", "ip_address", "user_agent",
            "details", "occurred_at",
        ], rows)

    def seed_outbox_event(self):
        rows = []
        for _ in range(self.n(100)):
            row_id = new_id()
            published = random.random() < 0.9
            created = FAKE.date_time_between("-90d", "now")
            rows.append((
                row_id, "USER", pick(self.ids["auth_user"]), "USER_REGISTERED",
                json.dumps({"email": FAKE.email()}), created,
                created + timedelta(seconds=random.randint(1, 60)) if published else None,
                0 if published else random.randint(1, 5),
            ))
        self.insert("outbox_event", [
            "id", "aggregate_type", "aggregate_id", "event_type", "payload", "created_at",
            "published_at", "attempts",
        ], rows)

    def seed_users(self):
        rows = []
        for auth_id in self.ids["auth_user"]:
            row_id = new_id()
            rows.append((
                row_id, auth_id, unique_username(),
                maybe([pick_media("profile")[0]], p=0.5),
                maybe([pick_media("banner")[0]], p=0.3),
                random.random() < 0.95,
            ))
        self.ids.setdefault("users", []).extend(r[0] for r in rows)
        self.insert("users", ["id", "auth_id", "username", "avatar", "banner", "active"], rows)

    def seed_person(self):
        rows = []
        for user_id in self.ids["users"]:
            row_id = new_id()
            rows.append((
                row_id, user_id, maybe(self.ids["contact"]), trunc(FAKE.name(), 60),
                gen_cpf(), FAKE.date_of_birth(minimum_age=18, maximum_age=75),
            ))
        self.ids.setdefault("person", []).extend(r[0] for r in rows)
        self.insert("person", ["id", "fk_users", "fk_contact", "name", "cpf", "birth_date"], rows)

    def seed_position(self):
        rows = [(new_id(), r["name"], r["accesses"]) for r in catalog("position")]
        self.ids["position"] = [r[0] for r in rows]
        self.insert("position", ["id", "name", "accesses"], rows)

    def seed_permission(self):
        rows = [
            (new_id(), r["permission_name"], r["permission_name"].split(":")[0].title(), r["description"])
            for r in catalog("permission")
        ]
        self.ids["permission"] = [r[0] for r in rows]
        self.insert("permission", ["id", "permission_name", "name", "description"], rows)

    def seed_position_permission(self):
        rows = []
        seen = set()
        for position_id in self.ids["position"]:
            for permission_id in random.sample(self.ids["permission"], k=random.randint(2, 6)):
                key = (position_id, permission_id)
                if key in seen:
                    continue
                seen.add(key)
                rows.append((new_id(), position_id, permission_id))
        self.insert("position_permission", ["id", "id_position", "id_permission"], rows)

    def seed_business_contact(self):
        rows = []
        for _ in range(self.n(80)):
            row_id = new_id()
            rows.append((row_id, trunc(FAKE.company_email(), 100), digits(11), FAKE.url()))
        self.ids.setdefault("business_contact", []).extend(r[0] for r in rows)
        self.insert("business_contact", ["id", "company_email", "phone", "website"], rows)

    def seed_company(self):
        rows = []
        for _ in range(self.n(80)):
            row_id = new_id()
            trade_name = trunc(FAKE.company(), 100)
            rows.append((
                row_id, pick(["UNDER_ANALYSIS", "APPROVED", "APPROVED", "REJECTED"]),
                pick(self.ids["address"]), pick(self.ids["business_contact"]),
                gen_cnpj(), trade_name, trunc(FAKE.company() + " " + FAKE.company_suffix(), 120),
            ))
        self.ids.setdefault("company", []).extend(r[0] for r in rows)
        self.insert("company", [
            "id", "status", "fk_address", "fk_business_contact", "cnpj", "trade_name",
            "corporate_name",
        ], rows)

    def seed_company_plans(self):
        rows = [(new_id(), r["name"], float(r["value"]), r["cycle"]) for r in catalog("company_plans")]
        self.ids["company_plans"] = [r[0] for r in rows]
        self.insert("company_plans", ["id", "name", "value", "cycle"], rows)

    def seed_company_positions(self):
        rows = []
        seen = set()
        for company_id in self.ids["company"]:
            for position_id in random.sample(self.ids["position"], k=random.randint(1, len(self.ids["position"]))):
                key = (company_id, position_id)
                if key in seen:
                    continue
                seen.add(key)
                rows.append((new_id(), company_id, position_id))
        self.insert("company_positions", ["id", "fk_company", "fk_position"], rows)

    def seed_user_company(self):
        rows = []
        seen = set()
        for user_id in self.ids["users"]:
            company_id = pick(self.ids["company"])
            key = (company_id, user_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append((new_id(), company_id, user_id, pick(self.ids["position"])))
        self.insert("user_company", ["id", "fk_company", "fk_users", "fk_position"], rows)

    def seed_supplier(self):
        rows = []
        for company_id in random.sample(self.ids["company"], k=min(len(self.ids["company"]), self.n(60))):
            row_id = new_id()
            rows.append((row_id, company_id, pick(["ACTIVE", "ACTIVE", "SUSPENDED", "DEACTIVATED"])))
        self.ids.setdefault("supplier", []).extend(r[0] for r in rows)
        self.insert("supplier", ["id", "fk_company", "status"], rows)

    def seed_subscription(self):
        rows = []
        for supplier_id in self.ids["supplier"]:
            row_id = new_id()
            start = FAKE.date_time_between("-2y", "-30d")
            rows.append((
                row_id, supplier_id, pick(self.ids["company_plans"]),
                pick(["PAID", "PAID", "IN_DEBT", "SUSPENDED"]), random.random() < 0.8,
                start, maybe([start + timedelta(days=365)], p=0.4),
            ))
        self.ids.setdefault("subscription", []).extend(r[0] for r in rows)
        self.insert("subscription", [
            "id", "fk_supplier", "fk_plan", "status", "auto_renewal", "start_date", "end_date",
        ], rows)

    def seed_charge(self):
        rows = []
        for _ in range(self.n(150)):
            row_id = new_id()
            due = FAKE.date_between("-1y", "+30d")
            paid = random.random() < 0.7
            rows.append((
                row_id, pick(self.ids["subscription"]), FAKE.pydecimal(left_digits=3, right_digits=2, positive=True),
                pick(["PIX", "BOLETO", "CREDIT_CARD", "TRANSFER"]),
                pick(["PAID", "PENDING", "CANCELED", "REFUNDED"]), due,
                FAKE.date_time_between(due, due + timedelta(days=5)) if paid else None,
            ))
        self.insert("charge", [
            "id", "fk_subscription", "amount", "payment_method", "status", "due_date", "payment_date",
        ], rows)

    def seed_model(self):
        rows = []
        for _ in range(self.n(40)):
            row_id = new_id()
            rows.append((
                row_id, trunc(FAKE.company(), 100), trunc(FAKE.bothify("Model-###??"), 100),
                FAKE.pydecimal(left_digits=3, right_digits=2, positive=True),
                FAKE.pydecimal(left_digits=2, right_digits=2, positive=True),
                FAKE.pydecimal(left_digits=1, right_digits=2, positive=True),
                FAKE.pydecimal(left_digits=2, right_digits=2, positive=True),
                pick(["APPROVED", "APPROVED", "UNDER_ANALYSIS", "REJECTED"]),
            ))
        self.ids.setdefault("model", []).extend(r[0] for r in rows)
        self.insert("model", [
            "id", "brand", "model", "power_wp", "efficiency", "dimension", "weight", "status",
        ], rows)

    def seed_offer(self):
        rows = []
        for _ in range(self.n(150)):
            row_id = new_id()
            rows.append((
                row_id, pick(self.ids["supplier"]), pick(self.ids["model"]),
                FAKE.pydecimal(left_digits=4, right_digits=2, positive=True), random.randint(0, 500),
                maybe([FAKE.date_time_between("now", "+1y")], p=0.5),
            ))
        self.ids.setdefault("offer", []).extend(r[0] for r in rows)
        self.insert("offer", [
            "id", "fk_supplier", "fk_model", "unit_price", "availability", "expiration_date",
        ], rows)

    def seed_inventory(self):
        # UNIQUE(fk_supplier, fk_model) no banco real -- nao pode repetir o par.
        max_pairs = len(self.ids["supplier"]) * len(self.ids["model"])
        target = min(self.n(150), max_pairs)
        rows = []
        seen = set()
        while len(rows) < target:
            pair = (pick(self.ids["supplier"]), pick(self.ids["model"]))
            if pair in seen:
                continue
            seen.add(pair)
            rows.append((new_id(), pair[0], pair[1], random.randint(0, 1000)))
        self.insert("inventory", ["id", "fk_supplier", "fk_model", "quantity"], rows)

    def seed_profession(self):
        rows = [
            (new_id(), r["name"], random.random() < 0.3, random.random() < 0.6)
            for r in catalog("profession")
        ]
        self.ids["profession"] = [r[0] for r in rows]
        self.insert("profession", ["id", "name", "accept_emergency_call", "requires_registration"], rows)

    def seed_technician(self):
        rows = []
        for person_id in random.sample(self.ids["person"], k=min(len(self.ids["person"]), self.n(100))):
            row_id = new_id()
            rows.append((row_id, person_id, trunc("CREA-" + FAKE.estado_sigla() + " " + digits(6), 60)))
        self.ids.setdefault("technician", []).extend(r[0] for r in rows)
        self.insert("technician", ["id", "fk_person", "crea"], rows)

    def seed_certification(self):
        rows = []
        for _ in range(self.n(20)):
            row_id = new_id()
            rows.append((
                row_id, pick(self.ids["technician"]),
                trunc(pick_text("certification_name", "name"), 255),
                pick_text("certification_description", "description"),
                trunc(FAKE.company(), 100),
                maybe([FAKE.date_time_between("now", "+3y")], p=0.7),
            ))
        self.ids.setdefault("certification", []).extend(r[0] for r in rows)
        self.insert("certification", ["id", "fk_technician", "type", "information", "issuer", "validity"], rows)

    def seed_professional_registration(self):
        rows = []
        for technician_id in self.ids["technician"]:
            row_id = new_id()
            rows.append((
                row_id, technician_id, pick(self.ids["profession"]),
                trunc(FAKE.estado_sigla(), 60), digits(8), FAKE.date_time_between("now", "+3y"),
            ))
        self.ids.setdefault("professional_registration", []).extend(r[0] for r in rows)
        self.insert("professional_registration", [
            "id", "fk_technician", "fk_profession", "council", "number", "expiration_date",
        ], rows)

    def seed_certification_record(self):
        rows = []
        for _ in range(self.n(60)):
            rows.append((new_id(), pick(self.ids["professional_registration"]), pick(self.ids["certification"])))
        self.insert("certification_record", ["id", "fk_professional_registration", "fk_certification"], rows)

    def seed_technician_affiliation(self):
        rows = []
        for technician_id in self.ids["technician"]:
            row_id = new_id()
            rows.append((
                row_id, pick(self.ids["company"]), technician_id,
                pick(["INDEPENDENT", "AFFILIATED", "PARTNER"]), random.random() < 0.9,
            ))
        self.ids.setdefault("technician_affiliation", []).extend(r[0] for r in rows)
        self.insert("technician_affiliation", [
            "id", "fk_company", "fk_technician", "affiliation_type", "active",
        ], rows)

    def seed_shift(self):
        rows = []
        for technician_id in self.ids["technician"]:
            for _ in range(random.randint(1, 3)):
                start = FAKE.date_time_between("-30d", "+30d")
                rows.append((
                    new_id(), technician_id, pick([
                        "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY",
                    ]), start, start + timedelta(hours=8),
                ))
        self.insert("shift", ["id", "fk_technician", "day_week", "start_date", "end_date"], rows)

    def seed_technical_course(self):
        rows = []
        for _ in range(self.n(15)):
            rows.append((
                new_id(), maybe(self.ids["company"], p=0.5), trunc(FAKE.catch_phrase(), 30),
                pick_text("business_note", "note"), FAKE.url(),
            ))
        self.insert("technical_course", ["id", "fk_company", "title", "information", "link"], rows)

    def seed_requester(self):
        rows = []
        for company_id in random.sample(self.ids["company"], k=min(len(self.ids["company"]), self.n(80))):
            rows.append((new_id(), company_id))
        self.ids.setdefault("requester", []).extend(r[0] for r in rows)
        self.insert("requester", ["id", "fk_company"], rows)

    def seed_local_unit(self):
        rows = []
        for _ in range(self.n(100)):
            row_id = new_id()
            rows.append((
                row_id, pick(self.ids["requester"]), pick(self.ids["address"]),
                maybe([f"Apto {random.randint(1, 200)}"], p=0.3), pick(["BUILDING", "HOUSE", "COMPLEX"]),
            ))
        self.ids.setdefault("local_unit", []).extend(r[0] for r in rows)
        self.insert("local_unit", ["id", "fk_requester", "fk_address", "complement", "location_type"], rows)

    def seed_unit_specifications(self):
        rows = []
        for _ in range(self.n(80)):
            rows.append((
                new_id(), pick(self.ids["local_unit"]), pick_text("business_note", "note"),
                pick_media("unit_specifications_photos")[0],
                FAKE.date_time_between("-1y", "now"),
            ))
        self.insert("unit_specifications", [
            "id", "fk_local_unit", "specifications", "location_photos", "date",
        ], rows)

    def seed_energy_bill(self):
        rows = []
        for _ in range(self.n(100)):
            rows.append((
                new_id(), pick(self.ids["local_unit"]),
                FAKE.pydecimal(left_digits=3, right_digits=2, positive=True),
                FAKE.pydecimal(left_digits=3, right_digits=2, positive=True),
            ))
        self.insert("energy_bill", ["id", "fk_local_unit", "consumption", "price"], rows)

    def seed_technical_project(self):
        rows = []
        for _ in range(self.n(100)):
            row_id = new_id()
            start = FAKE.date_time_between("-1y", "now")
            rows.append((
                row_id, pick(self.ids["requester"]), pick(self.ids["local_unit"]),
                pick(["OPEN", "IN_PROGRESS", "COMPLETED", "CANCELED"]), start,
                maybe([start + timedelta(days=random.randint(5, 90))], p=0.8),
            ))
        self.ids.setdefault("technical_project", []).extend(r[0] for r in rows)
        self.insert("technical_project", [
            "id", "fk_requester", "fk_local_unit", "status", "start_date", "end_date",
        ], rows)

    def seed_technical_service(self):
        rows = []
        for _ in range(self.n(150)):
            row_id = new_id()
            created = FAKE.date_time_between("-1y", "now")
            status = pick(["OPEN", "IN_PROGRESS", "COMPLETED", "COMPLETED", "CANCELED"])
            accepted = status != "OPEN"
            rows.append((
                row_id, pick(self.ids["technical_project"]), pick_text("technical_service_purpose", "purpose"), status,
                maybe([created + timedelta(days=1)], p=0.6), created,
                pick(self.ids["users"]) if accepted else None,
                (created + timedelta(days=1)) if accepted else None,
                (created + timedelta(days=10)) if status == "COMPLETED" else None,
            ))
        self.ids.setdefault("technical_service", []).extend(r[0] for r in rows)
        self.insert("technical_service", [
            "id", "fk_technical_project", "purpose", "status", "scheduled_date", "created_at",
            "accepted_by", "accepted_at", "end_date",
        ], rows)

    def seed_service_contract(self):
        rows = []
        for service_id in random.sample(self.ids["technical_service"], k=min(len(self.ids["technical_service"]), self.n(80))):
            rows.append((
                new_id(), service_id, maybe([pick(["12 meses", "24 meses", "60 meses"])]),
                maybe([FAKE.date_between("now", "+90d")], p=0.7), random.random() < 0.5,
                random.random() < 0.5,
            ))
        self.insert("service_contract", [
            "id", "fk_service", "warranty", "delivery_deadline", "insurance", "utility_approval",
        ], rows)

    def seed_service_executor(self):
        rows = []
        for service_id in self.ids["technical_service"]:
            for _ in range(random.randint(1, 2)):
                rows.append((
                    new_id(), service_id, pick(self.ids["technician_affiliation"]),
                    pick(["lead installer", "electrician", "supervisor", "helper"]),
                ))
        self.insert("service_executor", ["id", "fk_service", "fk_technician_affiliation", "function"], rows)

    def seed_professional_review(self):
        rows = []
        seen = set()
        completed_services = [
            s for s in self.ids["technical_service"]
        ]
        for _ in range(self.n(150)):
            technician_id = pick(self.ids["technician"])
            reviewer_id = pick(self.ids["users"])
            service_id = pick(completed_services)
            key = (reviewer_id, technician_id, service_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append((
                new_id(), technician_id, reviewer_id, service_id,
                FAKE.pydecimal(left_digits=1, right_digits=1, positive=True, max_value=5),
                pick_text("review_comment", "comment"), random.random() < 0.95, FAKE.date_time_between("-1y", "now"),
            ))
        self.insert("professional_review", [
            "id", "fk_professional", "fk_reviewer", "fk_service", "rating", "comment", "active", "created_at",
        ], rows)

    def seed_proposal(self):
        rows = []
        for _ in range(self.n(150)):
            row_id = new_id()
            created = FAKE.date_time_between("-1y", "now")
            rows.append((
                row_id, pick(self.ids["requester"]),
                pick(["AWAITING_SUPPLIER", "AWAITING_REQUESTER", "ACCEPTED", "REJECTED", "CANCELED"]),
                maybe([pick_text("business_note", "note")], p=0.5), None, created,
                maybe([created + timedelta(days=random.randint(1, 20))], p=0.6),
            ))
        self.ids.setdefault("proposal", []).extend(r[0] for r in rows)
        self.insert("proposal", [
            "id", "fk_requester", "status", "notes", "total_amount", "created_at", "updated_at",
        ], rows)

    def seed_proposal_item(self):
        rows = []
        for proposal_id in self.ids["proposal"]:
            for _ in range(random.randint(1, 3)):
                rows.append((
                    new_id(), proposal_id, pick(self.ids["offer"]), random.randint(1, 20),
                    maybe([FAKE.pydecimal(left_digits=4, right_digits=2, positive=True)], p=0.5),
                    maybe([FAKE.pydecimal(left_digits=2, right_digits=2, positive=True)], p=0.3),
                ))
        self.ids.setdefault("proposal_item", []).extend(r[0] for r in rows)
        self.insert("proposal_item", [
            "id", "fk_proposal", "fk_offer", "quantity", "negotiated_price", "discount",
        ], rows)

    def seed_proposal_unit(self):
        rows = []
        for proposal_item_id in self.ids["proposal_item"]:
            rows.append((
                new_id(), proposal_item_id, pick(self.ids["local_unit"]), random.randint(1, 5),
                maybe([pick_text("business_note", "note")], p=0.3),
            ))
        self.insert("proposal_unit", ["id", "fk_proposal_item", "fk_local_unit", "quantity", "note"], rows)

    def recompute_proposal_totals(self):
        # fn_proposal_total() nunca existiu no banco (nem em db/core/procedures,
        # que esta vazio) -- soma direto via proposal_item x offer.
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE proposal p
                SET total_amount = sub.total
                FROM (
                    SELECT pi.fk_proposal AS proposal_id,
                           SUM(pi.quantity * COALESCE(pi.negotiated_price, o.unit_price)
                               - COALESCE(pi.discount, 0)) AS total
                    FROM proposal_item pi
                    JOIN offer o ON o.id = pi.fk_offer
                    GROUP BY pi.fk_proposal
                ) sub
                WHERE p.id = sub.proposal_id
            """)
        print("  proposal.total_amount recalculado (soma de proposal_item x offer)")

    def seed_flux_log(self):
        rows = []
        for _ in range(self.n(300)):
            rows.append((
                new_id(), pick(self.ids["users"]),
                trunc(pick([
                    "LOGIN", "VIEW_PROPOSAL", "CREATE_PROPOSAL", "UPDATE_COMPANY",
                    "VIEW_CATALOG", "ACCEPT_PROPOSAL", "REJECT_PROPOSAL",
                ]), 255),
                FAKE.date_time_between("-1y", "now"),
            ))
        self.insert("flux_log", ["id", "fk_user", "action", "created_at"], rows)


USAGE = "uso: python -m scripts.dataload [rows]"

# auth_user e as tabelas que dependem dele vivem no banco do api-auth;
# users e tudo o resto vive no banco do api-core -- sao dois bancos
# Postgres fisicamente separados, entao precisam de duas conexoes. A fase
# auth roda primeiro porque users.auth_id referencia os IDs gerados aqui.
AUTH_STEPS = [
    "seed_auth_user", "seed_local_credential", "seed_federated_identity",
    "seed_one_time_token", "seed_auth_session",
    "seed_refresh_token", "seed_totp_factor", "seed_security_event", "seed_outbox_event",
]

CORE_STEPS = [
    "seed_address", "seed_contact", "seed_geolocalization",
    "seed_users", "seed_person",
    "seed_position", "seed_permission", "seed_position_permission",
    "seed_business_contact", "seed_company",
    "seed_company_plans", "seed_company_positions", "seed_user_company",
    "seed_supplier", "seed_subscription", "seed_charge",
    "seed_model", "seed_offer", "seed_inventory",
    "seed_profession", "seed_technician", "seed_certification",
    "seed_professional_registration", "seed_certification_record",
    "seed_technician_affiliation", "seed_shift", "seed_technical_course",
    "seed_requester", "seed_local_unit", "seed_unit_specifications", "seed_energy_bill",
    "seed_technical_project", "seed_technical_service",
    "seed_service_contract", "seed_service_executor", "seed_professional_review",
    "seed_proposal", "seed_proposal_item", "seed_proposal_unit", "recompute_proposal_totals",
    "seed_flux_log",
]


def run_phase(seeder: Seeder, target: str, step_names: list[str]) -> None:
    conn = connect(target)
    seeder.use_connection(conn)
    try:
        for name in step_names:
            print(f"[seed:{target}] {name} ...")
            getattr(seeder, name)()
        conn.commit()
        print(f"[seed:{target}] concluido e commitado.")
    except Exception:
        conn.rollback()
        print(f"[seed:{target}] FALHOU, alteracoes revertidas.")
        raise
    finally:
        conn.close()


def main():
    # rows e a referencia de escala (default: 1000)
    rows: int = int(sys.argv[1]) if len(sys.argv) > 1 else 1000

    scale = rows / 1000.0
    seeder = Seeder(scale)

    run_phase(seeder, "auth", AUTH_STEPS)
    run_phase(seeder, "core", CORE_STEPS)


if __name__ == "__main__":
    main()
