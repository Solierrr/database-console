"""
Gera e insere massa de dados de teste (Faker) no banco normalizado,
respeitando a ordem de dependencia de FK.

Uso:
    python -m scripts.seed.load_data --target analytics --rows 1000
"""

import argparse
import json
import random
import string
import uuid
from datetime import timedelta

from faker import Faker
from psycopg2.extras import execute_values

from scripts.db.connection import connect

fake = Faker("pt_BR")
Faker.seed(42)
random.seed(42)


def trunc(value: str, length: int) -> str:
    return value[:length]


def digits(n: int) -> str:
    return "".join(random.choices(string.digits, k=n))


def new_id() -> uuid.UUID:
    return uuid.uuid4()


def pick(seq):
    return random.choice(seq)


def maybe(seq, p=0.7):
    return pick(seq) if random.random() < p else None


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

    # ---- shared -------------------------------------------------------

    def seed_address(self):
        rows = []
        for _ in range(self.n(150)):
            row_id = new_id()
            rows.append((
                row_id,
                fake.estado_sigla(),
                trunc(fake.city(), 120),
                trunc(fake.bairro(), 120) if hasattr(fake, "bairro") else trunc(fake.city_suffix(), 120),
                digits(8),
                trunc(fake.street_name(), 200),
                str(random.randint(1, 9999)),
            ))
        self.ids.setdefault("address", []).extend(r[0] for r in rows)
        self.insert("address", ["id", "state", "city", "neighborhood", "zip_code", "street", "number"], rows)

    def seed_contact(self):
        rows = []
        for _ in range(self.n(150)):
            row_id = new_id()
            rows.append((row_id, trunc(fake.email(), 100), digits(11)))
        self.ids.setdefault("contact", []).extend(r[0] for r in rows)
        self.insert("contact", ["id", "email", "phone"], rows)

    def seed_geolocalization(self):
        rows = []
        for _ in range(self.n(80)):
            row_id = new_id()
            rows.append((
                row_id,
                maybe(self.ids["address"]),
                fake.pydecimal(left_digits=3, right_digits=7, positive=False),
                fake.pydecimal(left_digits=3, right_digits=7, positive=False),
            ))
        self.insert("geolocalization", ["id", "fk_address", "latitude", "longitude"], rows)

    def seed_media_assets(self, count: int) -> list[uuid.UUID]:
        rows = []
        ids = []
        for _ in range(count):
            row_id = new_id()
            ids.append(row_id)
            rows.append((row_id, fake.image_url(), uuid.uuid4().hex, fake.date_time_between("-2y", "now")))
        self.insert("media_asset", ["id", "url", "public_id", "created_at"], rows)
        return ids

    # ---- auth -----------------------------------------------------------

    def seed_auth_user(self):
        rows = []
        for _ in range(self.n(300)):
            row_id = new_id()
            rows.append((
                row_id,
                fake.unique.email(),
                maybe([fake.date_time_between("-2y", "now")]),
                pick(["ACTIVE", "ACTIVE", "ACTIVE", "LOCKED", "DISABLED"]),
                random.randint(0, 3),
                None,
                maybe([fake.date_time_between("-30d", "now")]),
                fake.date_time_between("-2y", "-1y"),
                fake.date_time_between("-1y", "now"),
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
                fake.sha256(),
                fake.date_time_between("-1y", "now"),
                random.random() < 0.05,
                fake.date_time_between("-2y", "-1y"),
                fake.date_time_between("-1y", "now"),
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
                fake.email(),
                random.random() < 0.8,
                fake.date_time_between("-1y", "now"),
                maybe([fake.date_time_between("-30d", "now")]),
            ))
        self.insert("federated_identity", [
            "id", "fk_user", "authority", "issuer", "subject", "email", "email_verified",
            "created_at", "last_login_at",
        ], rows)

    def seed_one_time_token(self):
        rows = []
        for _ in range(self.n(60)):
            row_id = new_id()
            created = fake.date_time_between("-90d", "now")
            rows.append((
                row_id,
                pick(self.ids["auth_user"]),
                fake.sha256().encode(),
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
            created = fake.date_time_between("-180d", "now")
            revoked = random.random() < 0.2
            rows.append((
                row_id,
                pick(self.ids["auth_user"]),
                fake.ipv4(),
                trunc(fake.user_agent(), 500),
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
                created = fake.date_time_between("-30d", "now")
                rows.append((
                    row_id, session_id, fake.sha256().encode(),
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
                row_id, auth_id, fake.sha256().encode()[:32], fake.sha256().encode()[:12],
                "key-" + uuid.uuid4().hex[:8], pick(["SHA1", "SHA256", "SHA512"]), 6, 30,
                maybe([fake.date_time_between("-1y", "now")]), maybe([random.randint(1, 999)]),
                fake.date_time_between("-1y", "-6M"), fake.date_time_between("-6M", "now"),
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
                fake.ipv4(),
                trunc(fake.user_agent(), 500),
                json.dumps({"note": fake.sentence()}),
                fake.date_time_between("-180d", "now"),
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
            created = fake.date_time_between("-90d", "now")
            rows.append((
                row_id, "USER", pick(self.ids["auth_user"]), "USER_REGISTERED",
                json.dumps({"email": fake.email()}), created,
                created + timedelta(seconds=random.randint(1, 60)) if published else None,
                0 if published else random.randint(1, 5),
            ))
        self.insert("outbox_event", [
            "id", "aggregate_type", "aggregate_id", "event_type", "payload", "created_at",
            "published_at", "attempts",
        ], rows)

    # ---- identity ---------------------------------------------------------

    def seed_users(self):
        rows = []
        for auth_id in self.ids["auth_user"]:
            row_id = new_id()
            rows.append((row_id, auth_id, maybe([fake.image_url()], p=0.5), random.random() < 0.95))
        self.ids.setdefault("users", []).extend(r[0] for r in rows)
        self.insert("users", ["id", "fk_auth_user", "avatar", "active"], rows)

    def seed_person(self):
        rows = []
        for user_id in self.ids["users"]:
            row_id = new_id()
            rows.append((
                row_id, user_id, maybe(self.ids["contact"]), trunc(fake.name(), 60),
                digits(11), fake.date_of_birth(minimum_age=18, maximum_age=75),
            ))
        self.ids.setdefault("person", []).extend(r[0] for r in rows)
        self.insert("person", ["id", "fk_user", "fk_contact", "name", "cpf", "birth_date"], rows)

    def seed_position(self):
        names = [("ADMIN", "full access"), ("MANAGER", "company management"),
                 ("TECHNICIAN", "field service"), ("SALES", "proposals and offers"),
                 ("SUPPORT", "customer support")]
        rows = [(new_id(), n, a) for n, a in names]
        self.ids["position"] = [r[0] for r in rows]
        self.insert("position", ["id", "name", "accesses"], rows)

    def seed_permission(self):
        perms = [
            ("company:read", "Ver empresas"), ("company:write", "Editar empresas"),
            ("proposal:read", "Ver propostas"), ("proposal:write", "Editar propostas"),
            ("catalog:read", "Ver catalogo"), ("catalog:write", "Editar catalogo"),
            ("service:read", "Ver servicos"), ("service:write", "Editar servicos"),
            ("billing:read", "Ver cobrancas"), ("billing:write", "Editar cobrancas"),
        ]
        rows = [(new_id(), code, code.split(":")[0].title(), desc) for code, desc in perms]
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

    def seed_user_photo(self):
        ids = self.seed_media_assets(self.n(40))
        rows = [(mid, pick(self.ids["users"]), pick(["PROFILE", "BANNER"])) for mid in ids]
        self.insert("user_photo", ["id", "fk_user", "type"], rows)

    # ---- company ---------------------------------------------------------

    def seed_business_contact(self):
        rows = []
        for _ in range(self.n(80)):
            row_id = new_id()
            rows.append((row_id, trunc(fake.company_email(), 100), digits(11), fake.url()))
        self.ids.setdefault("business_contact", []).extend(r[0] for r in rows)
        self.insert("business_contact", ["id", "company_email", "phone", "website"], rows)

    def seed_company(self):
        rows = []
        for _ in range(self.n(80)):
            row_id = new_id()
            trade_name = trunc(fake.company(), 100)
            rows.append((
                row_id, pick(["UNDER_ANALYSIS", "APPROVED", "APPROVED", "REJECTED"]),
                maybe(self.ids["address"]), maybe(self.ids["business_contact"]),
                digits(14), trade_name, trunc(fake.company() + " " + fake.company_suffix(), 120),
                pick(["INSTALLER", "DISTRIBUTOR", "MANUFACTURER", "RESELLER"]),
                trunc(f"{trade_name}-{uuid.uuid4().hex[:8]}".lower().replace(' ', '-'), 160),
            ))
        self.ids.setdefault("company", []).extend(r[0] for r in rows)
        self.insert("company", [
            "id", "status", "fk_address", "fk_business_contact", "cnpj", "trade_name",
            "corporate_name", "business_type", "slug",
        ], rows)

    def seed_company_photo(self):
        ids = self.seed_media_assets(self.n(40))
        rows = [(mid, pick(self.ids["company"]), pick(["PROFILE", "BANNER"])) for mid in ids]
        self.insert("company_photo", ["id", "fk_company", "type"], rows)

    def seed_company_plans(self):
        plans = [("Basic", 99.90, "MONTHLY"), ("Pro", 249.90, "MONTHLY"),
                  ("Pro Anual", 2399.90, "YEARLY"), ("Enterprise", 699.90, "QUARTERLY")]
        rows = [(new_id(), n, v, c) for n, v, c in plans]
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

    # ---- catalog -----------------------------------------------------------

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
            start = fake.date_time_between("-2y", "-30d")
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
            due = fake.date_between("-1y", "+30d")
            paid = random.random() < 0.7
            rows.append((
                row_id, pick(self.ids["subscription"]), fake.pydecimal(left_digits=3, right_digits=2, positive=True),
                pick(["PIX", "BOLETO", "CREDIT_CARD", "TRANSFER"]),
                pick(["PAID", "PENDING", "CANCELED", "REFUNDED"]), due,
                fake.date_time_between(due, due + timedelta(days=5)) if paid else None,
            ))
        self.insert("charge", [
            "id", "fk_subscription", "amount", "payment_method", "status", "due_date", "payment_date",
        ], rows)

    def seed_model(self):
        rows = []
        for _ in range(self.n(40)):
            row_id = new_id()
            rows.append((
                row_id, trunc(fake.company(), 100), trunc(fake.bothify("Model-###??"), 100),
                pick(["MONOCRYSTALLINE", "POLYCRYSTALLINE", "THIN_FILM"]),
                fake.pydecimal(left_digits=3, right_digits=2, positive=True),
                fake.pydecimal(left_digits=2, right_digits=2, positive=True),
                fake.pydecimal(left_digits=1, right_digits=2, positive=True),
                fake.pydecimal(left_digits=1, right_digits=2, positive=True),
                fake.pydecimal(left_digits=2, right_digits=2, positive=True),
                pick(["APPROVED", "APPROVED", "UNDER_ANALYSIS", "REJECTED"]),
            ))
        self.ids.setdefault("model", []).extend(r[0] for r in rows)
        self.insert("model", [
            "id", "brand", "model", "type", "power_wp", "efficiency", "width", "length", "weight", "status",
        ], rows)

    def seed_model_photo(self):
        ids = self.seed_media_assets(self.n(40))
        rows = [(mid, pick(self.ids["model"])) for mid in ids]
        self.insert("model_photo", ["id", "fk_model"], rows)

    def seed_offer(self):
        rows = []
        for _ in range(self.n(150)):
            row_id = new_id()
            slug = trunc(f"offer-{uuid.uuid4().hex[:12]}", 160)
            rows.append((
                row_id, pick(self.ids["supplier"]), pick(self.ids["model"]),
                fake.pydecimal(left_digits=4, right_digits=2, positive=True), random.randint(0, 500),
                maybe([fake.date_time_between("now", "+1y")], p=0.5), slug,
                maybe([fake.pydecimal(left_digits=2, right_digits=2, positive=True)], p=0.4),
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
                rows.append((offer_id, trunc(fake.estado_sigla() + "-" + fake.city(), 120)))
        self.insert("offer_service_region", ["fk_offer", "region"], list(set(rows)))

    def seed_offer_translation(self):
        rows = []
        for offer_id in self.ids["offer"]:
            for locale in random.sample(["pt-BR", "en-US", "es-ES"], k=random.randint(1, 2)):
                rows.append((
                    new_id(), offer_id, locale, trunc(fake.catch_phrase(), 160),
                    fake.text(200), maybe([fake.text(100)], p=0.4),
                ))
        self.insert("offer_translation", ["id", "fk_offer", "locale", "title", "description", "details"], rows)

    def seed_inventory(self):
        rows = []
        for _ in range(self.n(150)):
            rows.append((new_id(), pick(self.ids["supplier"]), pick(self.ids["model"]), random.randint(0, 1000)))
        self.insert("inventory", ["id", "fk_supplier", "fk_model", "quantity"], rows)

    # ---- professional -------------------------------------------------------

    def seed_profession(self):
        names = ["Eletricista", "Engenheiro Eletricista", "Tecnico em Eletronica",
                  "Instalador Solar", "Projetista", "Gestor de Obras", "Soldador", "Encanador"]
        rows = [(new_id(), n, random.random() < 0.3, random.random() < 0.6) for n in names]
        self.ids["profession"] = [r[0] for r in rows]
        self.insert("profession", ["id", "name", "accept_emergency_call", "requires_registration"], rows)

    def seed_certification(self):
        rows = []
        for _ in range(self.n(20)):
            row_id = new_id()
            rows.append((
                row_id, trunc(fake.bs().title(), 100), trunc(fake.company(), 100),
                fake.date_time_between("now", "+3y"), fake.text(150),
            ))
        self.ids.setdefault("certification", []).extend(r[0] for r in rows)
        self.insert("certification", ["id", "name", "issuer", "validity", "description"], rows)

    def seed_technician(self):
        rows = []
        for person_id in random.sample(self.ids["person"], k=min(len(self.ids["person"]), self.n(100))):
            row_id = new_id()
            slug = trunc(f"tech-{uuid.uuid4().hex[:12]}", 160)
            rows.append((row_id, person_id, trunc("CREA-" + fake.estado_sigla() + " " + digits(6), 60), slug))
        self.ids.setdefault("technician", []).extend(r[0] for r in rows)
        self.insert("technician", ["id", "fk_person", "crea", "slug"], rows)

    def seed_professional_registration(self):
        rows = []
        for technician_id in self.ids["technician"]:
            row_id = new_id()
            rows.append((
                row_id, technician_id, pick(self.ids["profession"]),
                trunc(fake.estado_sigla(), 60), digits(8), fake.date_time_between("now", "+3y"),
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
                start = fake.date_time_between("-30d", "+30d")
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
                new_id(), maybe(self.ids["company"], p=0.5), trunc(fake.catch_phrase(), 30),
                fake.text(150), fake.url(),
            ))
        self.insert("technical_course", ["id", "fk_company", "title", "information", "link"], rows)

    # ---- execution & unit ------------------------------------------------

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
        ids = self.seed_media_assets(self.n(60))
        rows = [(mid, pick(self.ids["local_unit"])) for mid in ids]
        self.insert("local_unit_photo", ["id", "fk_local_unit"], rows)

    def seed_unit_specifications(self):
        rows = []
        for _ in range(self.n(80)):
            rows.append((
                new_id(), pick(self.ids["local_unit"]), fake.text(150), fake.url(),
                fake.date_time_between("-1y", "now"),
            ))
        self.insert("unit_specifications", [
            "id", "fk_local_unit", "specifications", "location_photos", "date",
        ], rows)

    def seed_energy_bill(self):
        rows = []
        for _ in range(self.n(100)):
            rows.append((
                new_id(), pick(self.ids["local_unit"]),
                fake.pydecimal(left_digits=3, right_digits=2, positive=True),
                fake.pydecimal(left_digits=3, right_digits=2, positive=True),
                fake.image_url(), uuid.uuid4().hex,
            ))
        self.insert("energy_bill", ["id", "fk_local_unit", "consumption", "price", "photo_url", "photo_public_id"], rows)

    def seed_technical_project(self):
        rows = []
        for _ in range(self.n(100)):
            row_id = new_id()
            start = maybe([fake.date_time_between("-1y", "now")], p=0.8)
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
            created = fake.date_time_between("-1y", "now")
            status = pick(["OPEN", "IN_PROGRESS", "COMPLETED", "COMPLETED", "CANCELED"])
            accepted = status != "OPEN"
            rows.append((
                row_id, pick(self.ids["technical_project"]), trunc(fake.bs(), 200), status,
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
                maybe([fake.date_between("now", "+90d")], p=0.7), random.random() < 0.5,
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
                fake.pydecimal(left_digits=1, right_digits=1, positive=True, max_value=5),
                fake.text(120), random.random() < 0.95, fake.date_time_between("-1y", "now"),
            ))
        self.insert("professional_review", [
            "id", "fk_professional", "fk_reviewer", "fk_service", "rating", "comment", "active", "created_at",
        ], rows)

    # ---- proposal ----------------------------------------------------------

    def seed_proposal(self):
        rows = []
        for _ in range(self.n(150)):
            row_id = new_id()
            created = fake.date_time_between("-1y", "now")
            rows.append((
                row_id, pick(self.ids["requester"]),
                pick(["AWAITING_SUPPLIER", "AWAITING_REQUESTER", "ACCEPTED", "REJECTED", "CANCELED"]),
                maybe([fake.text(100)], p=0.5), None, created,
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
                    maybe([fake.pydecimal(left_digits=4, right_digits=2, positive=True)], p=0.5),
                    maybe([fake.pydecimal(left_digits=2, right_digits=2, positive=True)], p=0.3),
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
                maybe([fake.sentence()], p=0.3),
            ))
        self.insert("proposal_unit", ["id", "fk_proposal_item", "fk_local_unit", "quantity", "note"], rows)

    def recompute_proposal_totals(self):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE proposal SET total_amount = fn_proposal_total(id)")
        print(f"  proposal.total_amount recalculado via fn_proposal_total()")

    # ---- shared: flux_log --------------------------------------------------

    def seed_flux_log(self):
        rows = []
        for _ in range(self.n(300)):
            rows.append((
                new_id(), pick(self.ids["users"]),
                trunc(pick([
                    "LOGIN", "VIEW_PROPOSAL", "CREATE_PROPOSAL", "UPDATE_COMPANY",
                    "VIEW_CATALOG", "ACCEPT_PROPOSAL", "REJECT_PROPOSAL",
                ]), 255),
                fake.date_time_between("-1y", "now"),
            ))
        self.insert("flux_log", ["id", "fk_user", "action", "created_at"], rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=["core", "auth", "analytics"])
    parser.add_argument("--rows", type=int, default=1000, help="referencia de escala (default: 1000)")
    args = parser.parse_args()

    scale = args.rows / 1000.0
    conn = connect(args.target)
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
        seeder.seed_position_permission, seeder.seed_user_photo,
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
