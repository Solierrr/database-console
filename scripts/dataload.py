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


class Seeder:
    def __init__(self, conn, scale: float):
        self.conn = conn
        self.scale = scale
        self.ids = {}

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

    def seed_media_assets(self, count: int, pool: str) -> list[uuid.UUID]:
        rows = []
        ids = []
        for _ in range(count):
            row_id = new_id()
            ids.append(row_id)
            url, public_id = pick(media_pool(pool))
            rows.append((row_id, url, public_id, FAKE.date_time_between("-2y", "now")))
        self.insert("media_asset", ["id", "url", "public_id", "created_at"], rows)
        return ids

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
        for _ in range(self.n(50)):
            row_id = new_id()
            rows.append((
                row_id,
                pick(self.ids["auth_user"]),
                "FIREBASE",
                "https://securetoken.google.com/solaria",
                uuid.uuid4().hex,
                FAKE.email(),
                random.random() < 0.8,
                FAKE.date_time_between("-1y", "now"),
                maybe([FAKE.date_time_between("-30d", "now")]),
            ))
        self.insert("federated_identity", [
            "id", "fk_user", "authority", "issuer", "subject", "email", "email_verified",
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
            "id", "fk_user", "token_hash", "type", "expires_at", "consumed_at", "created_at",
        ], rows)

    def seed_auth_session(self):
        rows = []
        for _ in range(self.n(400)):
            row_id = new_id()
            created = FAKE.date_time_between("-180d", "now")
            revoked = random.random() < 0.2
            rows.append((
                row_id,
                pick(self.ids["auth_user"]),
                FAKE.ipv4(),
                trunc(FAKE.user_agent(), 500),
                pick(["web", "android", "ios"]),
                maybe([created], p=0.3),
                created,
                created + timedelta(days=random.randint(0, 30)),
                created + timedelta(days=30),
                created + timedelta(days=random.randint(1, 29)) if revoked else None,
                pick(["logout", "expired", "security"]) if revoked else None,
            ))
        self.ids.setdefault("auth_session", []).extend(r[0] for r in rows)
        self.insert("auth_session", [
            "id", "fk_user", "ip_address", "user_agent", "device", "mfa_completed_at",
            "created_at", "last_access_at", "expires_at", "revoked_at", "revocation_reason",
        ], rows)

    def seed_session_authentication_method(self):
        rows = []
        for session_id in self.ids["auth_session"]:
            for method in random.sample(["PASSWORD", "TOTP", "FEDERATED_FIREBASE"], k=random.randint(1, 2)):
                rows.append((session_id, method))
        self.insert("session_authentication_method", ["fk_session", "method"], rows)

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
            "id", "fk_session", "token_hash", "consumed_at", "revoked_at", "fk_replaced_by",
            "expires_at", "created_at",
        ], rows)
        if chain_ids:
            with self.conn.cursor() as cur:
                execute_values(
                    cur,
                    "UPDATE refresh_token AS rt SET fk_replaced_by = data.next_id "
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
            "id", "fk_user", "secret_ciphertext", "secret_nonce", "encryption_key_id", "algorithm",
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
                json.dumps({"note": FAKE.sentence()}),
                FAKE.date_time_between("-180d", "now"),
            ))
        self.insert("security_event", [
            "id", "fk_user", "fk_session", "event_type", "succeeded", "ip_address", "user_agent",
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
                digits(11), FAKE.date_of_birth(minimum_age=18, maximum_age=75),
            ))
        self.ids.setdefault("person", []).extend(r[0] for r in rows)
        self.insert("person", ["id", "fk_user", "fk_contact", "name", "cpf", "birth_date"], rows)

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
        self.insert("position_permission", ["id", "fk_position", "fk_permission"], rows)

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
                maybe(self.ids["address"]), maybe(self.ids["business_contact"]),
                digits(14), trade_name, trunc(FAKE.company() + " " + FAKE.company_suffix(), 120),
                pick(["INSTALLER", "DISTRIBUTOR", "MANUFACTURER", "RESELLER"]),
                trunc(f"{trade_name}-{uuid.uuid4().hex[:8]}".lower().replace(' ', '-'), 160),
            ))
        self.ids.setdefault("company", []).extend(r[0] for r in rows)
        self.insert("company", [
            "id", "status", "fk_address", "fk_business_contact", "cnpj", "trade_name",
            "corporate_name", "business_type", "slug",
        ], rows)

    def seed_company_photo(self):
        profile_ids = self.seed_media_assets(self.n(20), "profile")
        banner_ids = self.seed_media_assets(self.n(20), "banner")
        rows = [(mid, pick(self.ids["company"]), "PROFILE") for mid in profile_ids]
        rows += [(mid, pick(self.ids["company"]), "BANNER") for mid in banner_ids]
        self.insert("company_photo", ["id", "fk_company", "type"], rows)

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
        self.insert("user_company", ["id", "fk_company", "fk_user", "fk_position"], rows)

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
                pick(["MONOCRYSTALLINE", "POLYCRYSTALLINE", "THIN_FILM"]),
                FAKE.pydecimal(left_digits=3, right_digits=2, positive=True),
                FAKE.pydecimal(left_digits=2, right_digits=2, positive=True),
                FAKE.pydecimal(left_digits=1, right_digits=2, positive=True),
                FAKE.pydecimal(left_digits=1, right_digits=2, positive=True),
                FAKE.pydecimal(left_digits=2, right_digits=2, positive=True),
                pick(["APPROVED", "APPROVED", "UNDER_ANALYSIS", "REJECTED"]),
            ))
        self.ids.setdefault("model", []).extend(r[0] for r in rows)
        self.insert("model", [
            "id", "brand", "model", "type", "power_wp", "efficiency", "width", "length", "weight", "status",
        ], rows)

    def seed_model_photo(self):
        ids = self.seed_media_assets(self.n(40), "panels")
        rows = [(mid, pick(self.ids["model"])) for mid in ids]
        self.insert("model_photo", ["id", "fk_model"], rows)

    def seed_offer(self):
        rows = []
        for _ in range(self.n(150)):
            row_id = new_id()
            slug = trunc(f"offer-{uuid.uuid4().hex[:12]}", 160)
            rows.append((
                row_id, pick(self.ids["supplier"]), pick(self.ids["model"]),
                FAKE.pydecimal(left_digits=4, right_digits=2, positive=True), random.randint(0, 500),
                maybe([FAKE.date_time_between("now", "+1y")], p=0.5), slug,
                maybe([FAKE.pydecimal(left_digits=2, right_digits=2, positive=True)], p=0.4),
                maybe(["pt-BR", "en-US"], p=0.3), pick(["PENDING", "COMPLETED", "FAILED"]),
            ))
        self.ids.setdefault("offer", []).extend(r[0] for r in rows)
        self.insert("offer", [
            "id", "fk_supplier", "fk_model", "unit_price", "availability", "expiration_date", "slug",
            "discount_percentage", "source_locale", "translation_status",
        ], rows)

    def seed_offer_service_region(self):
        rows = []
        for offer_id in self.ids["offer"]:
            for _ in range(random.randint(1, 3)):
                rows.append((offer_id, trunc(FAKE.estado_sigla() + "-" + FAKE.city(), 120)))
        self.insert("offer_service_region", ["fk_offer", "region"], list(set(rows)))

    def seed_offer_translation(self):
        rows = []
        for offer_id in self.ids["offer"]:
            for locale in random.sample(["pt-BR", "en-US", "es-ES"], k=random.randint(1, 2)):
                rows.append((
                    new_id(), offer_id, locale, trunc(FAKE.catch_phrase(), 160),
                    FAKE.text(200), maybe([FAKE.text(100)], p=0.4),
                ))
        self.insert("offer_translation", ["id", "fk_offer", "locale", "title", "description", "details"], rows)

    def seed_inventory(self):
        rows = []
        for _ in range(self.n(150)):
            rows.append((new_id(), pick(self.ids["supplier"]), pick(self.ids["model"]), random.randint(0, 1000)))
        self.insert("inventory", ["id", "fk_supplier", "fk_model", "quantity"], rows)

    def seed_profession(self):
        rows = [
            (new_id(), r["name"], random.random() < 0.3, random.random() < 0.6)
            for r in catalog("profession")
        ]
        self.ids["profession"] = [r[0] for r in rows]
        self.insert("profession", ["id", "name", "accept_emergency_call", "requires_registration"], rows)

    def seed_certification(self):
        rows = []
        for _ in range(self.n(20)):
            row_id = new_id()
            rows.append((
                row_id, trunc(FAKE.bs().title(), 100), trunc(FAKE.company(), 100),
                FAKE.date_time_between("now", "+3y"), FAKE.text(150),
            ))
        self.ids.setdefault("certification", []).extend(r[0] for r in rows)
        self.insert("certification", ["id", "name", "issuer", "validity", "description"], rows)

    def seed_technician(self):
        rows = []
        for person_id in random.sample(self.ids["person"], k=min(len(self.ids["person"]), self.n(100))):
            row_id = new_id()
            slug = trunc(f"tech-{uuid.uuid4().hex[:12]}", 160)
            rows.append((row_id, person_id, trunc("CREA-" + FAKE.estado_sigla() + " " + digits(6), 60), slug))
        self.ids.setdefault("technician", []).extend(r[0] for r in rows)
        self.insert("technician", ["id", "fk_person", "crea", "slug"], rows)

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
                row_id, maybe(self.ids["company"], p=0.6), technician_id,
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
                FAKE.text(150), FAKE.url(),
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
                row_id, pick(self.ids["requester"]), maybe(self.ids["address"]),
                maybe([f"Apto {random.randint(1, 200)}"], p=0.3), pick(["BUILDING", "HOUSE", "COMPLEX"]),
            ))
        self.ids.setdefault("local_unit", []).extend(r[0] for r in rows)
        self.insert("local_unit", ["id", "fk_requester", "fk_address", "complement", "location_type"], rows)

    def seed_local_unit_photo(self):
        ids = self.seed_media_assets(self.n(60), "units")
        rows = [(mid, pick(self.ids["local_unit"])) for mid in ids]
        self.insert("local_unit_photo", ["id", "fk_local_unit"], rows)

    def seed_unit_specifications(self):
        rows = []
        for _ in range(self.n(80)):
            rows.append((
                new_id(), pick(self.ids["local_unit"]), FAKE.text(150),
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
                FAKE.image_url(), uuid.uuid4().hex,
            ))
        self.insert("energy_bill", ["id", "fk_local_unit", "consumption", "price", "photo_url", "photo_public_id"], rows)

    def seed_technical_project(self):
        rows = []
        for _ in range(self.n(100)):
            row_id = new_id()
            start = maybe([FAKE.date_time_between("-1y", "now")], p=0.8)
            rows.append((
                row_id, maybe(self.ids["requester"]), maybe(self.ids["local_unit"]),
                maybe(["OPEN", "IN_PROGRESS", "COMPLETED", "CANCELED"], p=0.9), start,
                (start + timedelta(days=random.randint(5, 90))) if start else None,
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
                row_id, pick(self.ids["technical_project"]), trunc(FAKE.bs(), 200), status,
                maybe([created + timedelta(days=1)], p=0.6), created,
                pick(self.ids["users"]) if accepted else None,
                (created + timedelta(days=1)) if accepted else None,
                (created + timedelta(days=10)) if status == "COMPLETED" else None,
            ))
        self.ids.setdefault("technical_service", []).extend(r[0] for r in rows)
        self.insert("technical_service", [
            "id", "fk_technical_project", "purpose", "status", "scheduled_date", "created_at",
            "fk_accepted_by", "accepted_at", "end_date",
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
                FAKE.text(120), random.random() < 0.95, FAKE.date_time_between("-1y", "now"),
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
                maybe([FAKE.text(100)], p=0.5), None, created,
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
                maybe([FAKE.sentence()], p=0.3),
            ))
        self.insert("proposal_unit", ["id", "fk_proposal_item", "fk_local_unit", "quantity", "note"], rows)

    def recompute_proposal_totals(self):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE proposal SET total_amount = fn_proposal_total(id)")
        print(f"  proposal.total_amount recalculado via fn_proposal_total()")

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


USAGE = "uso: python -m scripts.dataload <core|auth|analytics> [rows]"
TARGETS = ("core", "auth", "analytics")


def main():
    if len(sys.argv) < 2:
        sys.exit(USAGE)

    target: str = sys.argv[1]
    if target not in TARGETS:
        sys.exit(f"target invalido: {target!r}. {USAGE}")

    # rows e a referencia de escala (default: 1000)
    rows: int = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

    scale = rows / 1000.0
    conn = connect(target)
    seeder = Seeder(conn, scale)

    steps = [
        seeder.seed_address, seeder.seed_contact, seeder.seed_geolocalization,
        seeder.seed_auth_user, seeder.seed_local_credential,
        # users precisa existir antes de auth_session para a trigger de
        # DAU (fn_log_access) conseguir resolver fk_auth_user -> users.id.
        seeder.seed_users, seeder.seed_person,
        seeder.seed_federated_identity,
        seeder.seed_one_time_token, seeder.seed_auth_session, seeder.seed_session_authentication_method,
        seeder.seed_refresh_token, seeder.seed_totp_factor, seeder.seed_security_event,
        seeder.seed_outbox_event,
        seeder.seed_position, seeder.seed_permission,
        seeder.seed_position_permission,
        seeder.seed_business_contact, seeder.seed_company, seeder.seed_company_photo,
        seeder.seed_company_plans, seeder.seed_company_positions, seeder.seed_user_company,
        seeder.seed_supplier, seeder.seed_subscription, seeder.seed_charge,
        seeder.seed_model, seeder.seed_model_photo, seeder.seed_offer,
        seeder.seed_offer_service_region, seeder.seed_offer_translation, seeder.seed_inventory,
        seeder.seed_profession, seeder.seed_certification, seeder.seed_technician,
        seeder.seed_professional_registration, seeder.seed_certification_record,
        seeder.seed_technician_affiliation, seeder.seed_shift, seeder.seed_technical_course,
        seeder.seed_requester, seeder.seed_local_unit, seeder.seed_local_unit_photo,
        seeder.seed_unit_specifications, seeder.seed_energy_bill,
        seeder.seed_technical_project, seeder.seed_technical_service,
        seeder.seed_service_contract, seeder.seed_service_executor, seeder.seed_professional_review,
        seeder.seed_proposal, seeder.seed_proposal_item, seeder.seed_proposal_unit,
        seeder.recompute_proposal_totals,
        seeder.seed_flux_log,
    ]

    try:
        for step in steps:
            print(f"[seed] {step.__name__} ...")
            step()
        conn.commit()
        print("[seed] concluido e commitado.")
    except Exception:
        conn.rollback()
        print("[seed] FALHOU, alteracoes revertidas.")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
