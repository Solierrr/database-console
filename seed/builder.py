import csv
import json
import random
import re
import unicodedata
import uuid
from collections import Counter, OrderedDict
from datetime import datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import NamedTuple

NAMESPACE = uuid.UUID('6f1c1b2e-5d3a-4f7e-9a41-0c2d8b7e5a10')
CATALOG_DIR = Path(__file__).resolve().parents[1] / 'scripts' / 'data' / 'catalog'

CORE_TABLES = [
    'address', 'geolocation', 'business_contact', 'company', 'user_account', 'person', 'technician',
    'company_position', 'position_permission', 'user_company', 'requester', 'supplier', 'technical_company', 'subscription',
    'brand', 'model', 'offer', 'offer_translation', 'inventory', 'local_unit', 'unit_specification',
    'proposal', 'proposal_item', 'proposal_unit', 'cart', 'cart_item', 'purchase_order', 'order_item', 'order_payment',
    'professional_registration', 'professional_onboarding', 'certification',
    'certification_record', 'technician_affiliation', 'technical_project', 'technical_service',
    'service_executor', 'project_member', 'project_activity', 'project_history', 'project_photo', 'professional_review', 'user_photo', 'company_photo', 'local_unit_photo',
    'model_photo', 'platform_admin',
]
AUTH_TABLES = ['auth_user', 'local_credential']
REFERENCE_TABLES = {'job_position': 'name', 'profession': 'name', 'company_plan': 'name', 'permission': 'permission_name'}

FIRST_NAMES = [
    'Ana', 'Bruno', 'Carla', 'Daniel', 'Elisa', 'Fabio', 'Gabriela', 'Henrique', 'Isabela', 'Joao',
    'Karina', 'Lucas', 'Mariana', 'Nelson', 'Olivia', 'Paulo', 'Renata', 'Sergio', 'Tatiana', 'Vinicius',
    'Amanda', 'Bernardo', 'Camila', 'Diego', 'Fernanda', 'Gustavo', 'Helena', 'Igor', 'Juliana', 'Leandro',
    'Marcos', 'Natalia', 'Otavio', 'Patricia', 'Rafael', 'Silvia', 'Thiago', 'Valeria', 'Wesley', 'Yara',
]
LAST_NAMES = [
    'Almeida', 'Barbosa', 'Cardoso', 'Dias', 'Esteves', 'Ferreira', 'Gomes', 'Hernandes', 'Ibrahim', 'Jesus',
    'Lacerda', 'Macedo', 'Nogueira', 'Oliveira', 'Pereira', 'Queiroz', 'Ribeiro', 'Siqueira', 'Teixeira', 'Valente',
    'Andrade', 'Batista', 'Carvalho', 'Duarte', 'Farias', 'Guimaraes', 'Holanda', 'Lopes', 'Moreira', 'Nascimento',
    'Pinheiro', 'Rocha', 'Santana', 'Tavares', 'Vasconcelos', 'Azevedo', 'Brito', 'Coelho', 'Freitas', 'Lima',
]
COUNCILS = ['CREA-SP', 'CREA-MG', 'CREA-PR', 'CREA-RS', 'CREA-PE', 'CREA-GO', 'CFT-SP', 'CFT-MG']
SEGMENT_STREET_NUMBERS = range(10, 2400)


class Ref(NamedTuple):
    table: str
    name: str


def uid(*parts):
    return uuid.uuid5(NAMESPACE, ':'.join(str(part) for part in parts))


def slugify(value):
    text = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def read_catalog(name, column):
    with open(CATALOG_DIR / f'{name}.csv', newline='', encoding='utf-8') as handle:
        return [row[column] for row in csv.DictReader(handle)]


def check_digit(digits, weights):
    total = sum(int(d) * w for d, w in zip(digits, weights))
    rest = total % 11
    return '0' if rest < 2 else str(11 - rest)


def make_cpf(rng):
    base = ''.join(str(rng.randint(0, 9)) for _ in range(9))
    first = check_digit(base, range(10, 1, -1))
    second = check_digit(base + first, range(11, 1, -1))
    return base + first + second


def make_cnpj(rng):
    base = ''.join(str(rng.randint(0, 9)) for _ in range(8)) + '0001'
    first = check_digit(base, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    second = check_digit(base + first, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return base + first + second


class Dataset:
    def __init__(self):
        self.core = OrderedDict((table, []) for table in CORE_TABLES)
        self.auth = OrderedDict((table, []) for table in AUTH_TABLES)
        self.image_report = []
        self.notes = []

    def counts(self):
        return {name: len(rows) for name, rows in {**self.core, **self.auth}.items() if rows}


class Builder:
    def __init__(self, plan, pool, today):
        self.plan = plan
        self.pool = pool
        self.today = today
        self.rng = random.Random(plan['rng_seed'])
        self.data = Dataset()
        self.cities = {city['key']: city for city in plan['cities']}
        self.usernames = set()
        self.slugs = set()
        self.company_admin = {}
        self.company_staff = {}
        self.dev_users = {}
        self.units_by_company = {}
        self.offers = []
        self.affiliations = []
        self.positions = {name: Ref('job_position', name) for name in read_catalog('job_position', 'name')}
        self.domain = plan['auth']['email_domain']

    # ---------- helpers ----------
    def add(self, table, row):
        target = self.data.core if table in self.data.core else self.data.auth
        target[table].append(row)
        return row

    def when(self, days=0, hours=0):
        base = datetime.combine(self.today, time(12, 0), tzinfo=timezone.utc)
        return base + timedelta(days=days, hours=hours)

    def phone(self):
        return '11' + ''.join(str(self.rng.randint(0, 9)) for _ in range(9))

    def address(self, city_key, label, owner_company_id=None):
        city = self.cities[city_key]
        address_id = uid('address', label)
        zip_code = city['zip'] + ''.join(str(self.rng.randint(0, 9)) for _ in range(3))
        self.add('address', {
            'id': address_id, 'state': city['state'], 'city': city['name'],
            'neighborhood': self.rng.choice(['Centro', 'Jardim America', 'Vila Nova', 'Boa Vista', 'Santa Cruz']),
            'zip_code': zip_code, 'street': self.rng.choice(self.plan['streets']),
            'number': str(self.rng.choice(SEGMENT_STREET_NUMBERS)),
            'owner_company_id': owner_company_id,
        })
        self.add('geolocation', {
            'id': uid('geo', label), 'address_id': address_id,
            'latitude': round(city['lat'] + self.rng.uniform(-0.06, 0.06), 7),
            'longitude': round(city['lon'] + self.rng.uniform(-0.06, 0.06), 7),
        })
        return address_id

    def person_name(self):
        for _ in range(500):
            first, last = self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES)
            username = slugify(f'{first}_{last}').replace('-', '_')
            if username not in self.usernames:
                self.usernames.add(username)
                return f'{first} {last}', username
        raise RuntimeError('Sem nomes unicos suficientes')

    def user(self, key, avatar_category, company_id=None, position=None, username=None):
        if username is None:
            name, username = self.person_name()
        else:
            self.usernames.add(username)
            name = ' '.join(part.capitalize() for part in username.split('_'))
        user_id = uid('user', key)
        auth_id = uid('auth', key)
        avatar = self.pool.unique(avatar_category)
        banner = self.pool.repeat_any(['users/banners/landscapes', 'users/banners/colors', 'users/banners/abstract'], self.rng)
        self.add('user_account', {
            'id': user_id, 'auth_id': auth_id, 'username': username, 'is_active': True,
            'managed_by_company_id': company_id if company_id and position != 'ADMIN' else None,
            'avatar': self.pool.url(avatar) if avatar else None,
            'banner': self.pool.url(banner) if banner else None,
        })
        self.add('auth_user', {
            'id': auth_id, 'primary_email': f'{username}@{self.domain}',
            'email_verified_at': self.when(-30), 'status': 'ACTIVE',
        })
        self.add('local_credential', {
            'auth_user_id': auth_id, 'password_hash': self.plan['auth']['password_hash'], 'is_password_change_required': False,
        })
        person_id = uid('person', key)
        self.add('person', {
            'id': person_id, 'user_id': user_id, 'contact_id': None, 'name': name,
            'cpf': make_cpf(self.rng), 'birth_date': (self.today - timedelta(days=self.rng.randint(25 * 365, 58 * 365))),
        })
        for image, kind in ((avatar, 'PROFILE'), (banner, 'BANNER')):
            if image:
                self.add('user_photo', {
                    'id': uid('user_photo', key, kind), 'user_id': user_id, 'type': kind,
                    'url': self.pool.url(image), 'public_id': self.pool.public_id(image), 'created_at': self.when(-20),
                    **self.pool.crop_columns(image),
                })
        if company_id is not None:
            self.add('user_company', {
                'id': uid('user_company', key), 'company_id': company_id, 'user_id': user_id,
                'job_position_id': self.positions[position],
            })
        return user_id, person_id, name

    def company(self, key, name, ctype, city_key, banner_theme, status='APPROVED'):
        company_id = uid('company', key)
        address_id = self.address(city_key, f'company:{key}', company_id)
        contact_id = uid('contact', key)
        self.add('business_contact', {
            'id': contact_id, 'company_email': f'contato@{key}.{self.domain}'[:100], 'phone': self.phone(),
            'website': f'https://{key}.{self.domain}',
        })
        self.add('company', {
            'id': company_id, 'status': status, 'type': ctype, 'address_id': address_id,
            'business_contact_id': contact_id, 'cnpj': make_cnpj(self.rng), 'trade_name': name[:120],
            'corporate_name': f'{name} Ltda'[:120], 'slug': key,
        })
        logo = self.pool.unique('enterprises/pfp')
        banner = self.pool.unique(f'enterprises/banners/{banner_theme}')
        for image, kind in ((logo, 'PROFILE'), (banner, 'BANNER')):
            if image:
                self.add('company_photo', {
                    'id': uid('company_photo', key, kind), 'company_id': company_id, 'type': kind,
                    'url': self.pool.url(image), 'public_id': self.pool.public_id(image), 'created_at': self.when(-40),
                    **self.pool.crop_columns(image),
                })
        return company_id

    def company_positions(self, company_id, names):
        for name in names:
            self.add('company_position', {
                'id': uid('company_position', company_id, name), 'company_id': company_id, 'job_position_id': self.positions[name],
            })

    # ---------- groups ----------
    def build(self):
        self.build_position_permissions()
        self.build_demandants()
        self.build_suppliers()
        self.build_technical_companies()
        self.build_platform_admins()
        self.build_catalog()
        self.build_technicians()
        self.build_proposals()
        self.build_orders()
        self.build_services()
        self.build_dev_accounts()
        self.build_projects()
        self.build_test_account()
        self.data.image_report = self.pool.report()
        return self.data

    def build_position_permissions(self):
        # Concessoes padrao por cargo (catalogo `permission` vem das migracoes). Sem sorteio: nao desloca nenhum dado.
        for position, permissions in self.plan.get('position_permissions', {}).items():
            for permission in permissions:
                self.add('position_permission', {
                    'id': uid('position_permission', position, permission),
                    'job_position_id': self.positions[position], 'permission_id': Ref('permission', permission),
                })

    def build_demandants(self):
        overrides = self.plan.get('company_status_overrides', {})
        for entry in self.plan['demandants']:
            key = entry['key']
            company_id = self.company(key, entry['name'], 'REQUESTER', entry['cities'][0], entry['banner_theme'],
                                      overrides.get(key, 'APPROVED'))
            requester_id = uid('requester', key)
            self.add('requester', {'id': requester_id, 'company_id': company_id, 'business_type': entry['segment']})
            self.company_positions(company_id, ['ADMIN', 'MANAGER', 'SUPPORT'])
            admin_id, _, _ = self.user(f'{key}:admin', 'users/pfp/suitman', company_id, 'ADMIN')
            self.company_admin[company_id] = admin_id
            manager_id, _, _ = self.user(f'{key}:manager', 'users/pfp/clients', company_id, 'MANAGER')
            support_id, _, _ = self.user(f'{key}:support', 'users/pfp/clients', company_id, 'SUPPORT')
            self.company_staff[company_id] = {'MANAGER': manager_id, 'SUPPORT': support_id}
            units = []
            for index in range(entry['units']):
                units.append(self.local_unit(entry, requester_id, index))
            self.units_by_company[company_id] = {'requester': requester_id, 'units': units, 'segment': entry['segment']}

    def local_unit(self, entry, requester_id, index):
        key, segment = entry['key'], entry['segment']
        city_key = entry['cities'][index % len(entry['cities'])]
        unit_id = uid('unit', key, index)
        address_id = self.address(city_key, f'unit:{key}:{index}', uid('company', key))
        self.add('local_unit', {
            'id': unit_id, 'requester_id': requester_id, 'address_id': address_id,
            'complement': f'Unidade {index + 1} - {self.cities[city_key]["name"]}', 'location_type': entry['location_type'],
        })
        low, high = entry['kwh']
        kwh = self.rng.randrange(low, high, 100)
        self.add('unit_specification', {
            'id': uid('unit_spec', key, index), 'local_unit_id': unit_id,
            'specifications': (f'Consumo medio mensal {kwh} kWh; area de cobertura {self.rng.randrange(400, 6000, 50)} m2; '
                               f'tarifa {self.rng.choice(["B3", "A4", "B1"])}; padrao {self.rng.choice(["monofasico", "bifasico", "trifasico"])}')[:255],
            'location_photos': None, 'date': self.when(-self.rng.randint(5, 200)),
        })
        for kind in ('main', 'banner'):
            image = self.pool.unique(f'units/{segment}/{kind}')
            if image:
                self.add('local_unit_photo', {
                    'id': uid('unit_photo', key, index, kind), 'local_unit_id': unit_id,
                    'type': 'BANNER' if kind == 'banner' else 'GALLERY', 'is_primary': kind == 'main',
                    'url': self.pool.url(image), 'public_id': self.pool.public_id(image), 'created_at': self.when(-15),
                })
        for position, image in enumerate(self.pool.sample(f'units/{segment}/gallery', 4, self.rng)):
            self.add('local_unit_photo', {
                'id': uid('unit_photo', key, index, 'gallery', position), 'local_unit_id': unit_id, 'type': 'GALLERY',
                'is_primary': False, 'url': self.pool.url(image), 'public_id': self.pool.public_id(image), 'created_at': self.when(-15),
            })
        return unit_id

    def build_suppliers(self):
        self.suppliers = []
        for entry in self.plan['suppliers']:
            key = entry['key']
            company_id = self.company(key, entry['name'], 'SUPPLIER', entry['city'], entry['banner_theme'])
            supplier_id = uid('supplier', key)
            self.add('supplier', {
                'id': supplier_id, 'company_id': company_id, 'status': 'ACTIVE', 'business_type': entry['business_type'],
            })
            expired = entry['subscription'] == 'expired'
            self.add('subscription', {
                'id': uid('subscription', key), 'supplier_id': supplier_id, 'company_plan_id': Ref('company_plan', 'Pro'),
                'status': 'IN_DEBT' if expired else 'PAID', 'has_auto_renewal': not expired,
                'starts_at': self.when(-120), 'ends_at': self.when(-10 if expired else 245),
            })
            self.company_positions(company_id, ['ADMIN', 'MANAGER', 'SALES'])
            self.user(f'{key}:admin', 'users/pfp/suitman', company_id, 'ADMIN')
            self.user(f'{key}:manager', 'users/pfp/staff', company_id, 'MANAGER')
            self.user(f'{key}:sales', 'users/pfp/staff', company_id, 'SALES')
            self.suppliers.append({**entry, 'company_id': company_id, 'supplier_id': supplier_id})

    def build_technical_companies(self):
        self.technical_companies = []
        for entry in self.plan['technical_companies']:
            key = entry['key']
            company_id = self.company(key, entry['name'], 'SUPPLIER', entry['city'], entry['banner_theme'])
            self.add('supplier', {
                'id': uid('supplier', key), 'company_id': company_id, 'status': 'ACTIVE', 'business_type': 'INSTALADORA',
            })
            self.add('technical_company', {'id': uid('technical_company', key), 'company_id': company_id})
            self.company_positions(company_id, ['ADMIN', 'MANAGER', 'TECHNICIAN', 'SUPPORT'])
            self.user(f'{key}:admin', 'users/pfp/suitman', company_id, 'ADMIN')
            self.user(f'{key}:manager', 'users/pfp/staff', company_id, 'MANAGER')
            self.user(f'{key}:support', 'users/pfp/staff', company_id, 'SUPPORT')
            self.technical_companies.append({**entry, 'company_id': company_id})

    def build_platform_admins(self):
        for index in range(self.plan['platform_admins']):
            user_id, _, _ = self.user(f'platform-admin:{index}', 'users/pfp/staff')
            self.add('platform_admin', {'id': uid('platform_admin', index), 'user_id': user_id, 'created_at': self.when(-90)})

    def build_dev_accounts(self):
        # Contas fixas (uma por cargo) para entrar no web sem procurar nomes aleatorios. Criadas no fim do build
        # para nao deslocar nenhum dado sorteado antes delas.
        for group in self.plan.get('dev_accounts', []):
            company_id = uid('company', group['company'])
            for username, position in group['accounts']:
                category = 'users/pfp/suitman' if position == 'ADMIN' else 'users/pfp/clients'
                if position == 'TECHNICIAN':
                    user_id = self.dev_technician(group['company'], company_id, username)
                else:
                    user_id, _, _ = self.user(f'dev:{username}', category, company_id, position, username=username)
                self.dev_users.setdefault(company_id, {})[position] = user_id
        if self.plan.get('dev_platform_admin'):
            user_id, _, _ = self.user('dev:platform-admin', 'users/pfp/staff', username=self.plan['dev_platform_admin'])
            self.add('platform_admin', {'id': uid('platform_admin', 'dev'), 'user_id': user_id, 'created_at': self.when(-90)})

    def build_test_account(self):
        account = self.plan.get('dev_test_account')
        if not account:
            return
        groups = self.plan.get('dev_accounts', [])
        technical = next(group for group in groups if any(role == 'TECHNICIAN' for _, role in group['accounts']))
        username = account['username']
        user_id = self.dev_technician(technical['company'], uid('company', technical['company']), username)
        auth_id = uid('auth', f'dev:{username}')
        next(row for row in self.data.core['user_account'] if row['id'] == user_id)['managed_by_company_id'] = None
        next(row for row in self.data.auth['auth_user'] if row['id'] == auth_id)['primary_email'] = account['email']
        next(row for row in self.data.auth['local_credential'] if row['auth_user_id'] == auth_id)['password_hash'] = account['password_hash']
        next(row for row in self.data.core['user_company'] if row['user_id'] == user_id)['job_position_id'] = self.positions['ADMIN']
        for group in groups:
            if group['company'] != technical['company']:
                self.add('user_company', {
                    'id': uid('user_company', f'dev:{username}', group['company']),
                    'company_id': uid('company', group['company']), 'user_id': user_id,
                    'job_position_id': self.positions['ADMIN'],
                })
        self.add('platform_admin', {'id': uid('platform_admin', 'dev-test'), 'user_id': user_id, 'created_at': self.when(-90)})
        for project in self.data.core['technical_project']:
            self.add('project_member', {
                'id': uid('project_member', project['id'], user_id), 'technical_project_id': project['id'],
                'user_id': user_id, 'role': 'MANAGER', 'function_name': 'Responsável de teste',
                'is_active': True, 'joined_at': self.when(-20),
            })

    def approved_onboarding(self, user_id, technician_id, council, number, expiration):
        """Perfil de onboarding aprovado: é o que o login mobile exige de um profissional (api-core, `eligibility`).
        Não sorteia nada, então os demais dados do seed não mudam. `professionId` fica nulo porque a profissão só é
        resolvida (por nome) na hora de gravar; a profissão do técnico está em `professional_registration`."""
        person = next(row for row in reversed(self.data.core['person']) if row['user_id'] == user_id)
        user = next(row for row in reversed(self.data.core['user_account']) if row['id'] == user_id)
        draft = json.dumps({
            'revision': 1, 'name': person['name'], 'cpf': person['cpf'], 'birthDate': person['birth_date'].isoformat(),
            'email': f"{user['username']}@{self.domain}", 'phone': None, 'professionId': None,
            'council': council, 'registrationNumber': number,
            'registrationExpiration': expiration.date().isoformat(), 'documentIds': [],
        }, default=str)
        self.add('professional_onboarding', {
            'id': uid('professional_onboarding', technician_id), 'auth_id': user['auth_id'], 'user_id': user_id,
            'technician_id': technician_id, 'revision': 1, 'approved_version': 1,
            'draft_json': draft, 'approved_json': draft, 'is_suspended': False,
        })

    def dev_technician(self, company_key, company_id, username):
        user_id, person_id, name = self.user(f'dev:{username}', 'users/pfp/professionals', company_id, 'TECHNICIAN', username=username)
        technician_id = uid('technician', 'dev', username)
        registration_id = uid('registration', 'dev', username)
        profession = next(iter(self.plan['technicians']['professions']))
        self.add('technician', {
            'id': technician_id, 'person_id': person_id, 'crea': 'CREA-SP 100001', 'slug': f'{slugify(name)}-dev', 'status': 'APPROVED',
        })
        self.add('professional_registration', {
            'id': registration_id, 'technician_id': technician_id, 'profession_id': Ref('profession', profession),
            'council': 'CREA-SP', 'number': '100001', 'expires_at': self.when(720),
        })
        self.approved_onboarding(user_id, technician_id, 'CREA-SP', '100001', self.when(720))
        self.add('technician_affiliation', {
            'id': uid('affiliation', 'dev', username), 'company_id': company_id, 'technician_id': technician_id,
            'affiliation_type': 'AFFILIATED', 'is_active': True,
        })
        return user_id

    # ---------- projects ----------
    def build_projects(self):
        """Enriquece os projetos criados por build_services: nome, descrição, situação, local, membros, atividades,
        histórico e fotos. Roda no fim e usa um RNG próprio, então nenhum dado sorteado antes muda."""
        rng = random.Random(f"{self.plan['rng_seed']}:projects")
        core = self.data.core
        addresses = {row['id']: row for row in core['address']}
        units = {row['id']: row for row in core['local_unit']}
        companies = {row['id']: row for row in core['company']}
        affiliation_user = {item['affiliation']: item['user'] for item in self.technicians}
        executors = {}
        for row in core['service_executor']:
            executors.setdefault(row['technical_service_id'], []).append(row)
        services = {}
        for row in core['technical_service']:
            services.setdefault(row['technical_project_id'], []).append(row)

        # a conta de técnico de desenvolvimento participa de alguns projetos, para a visão do técnico não ficar vazia
        dev_technician = next((users['TECHNICIAN'] for users in self.dev_users.values() if 'TECHNICIAN' in users), None)
        dev_projects = {row['id'] for row in rng.sample(core['technical_project'], min(5, len(core['technical_project'])))}             if dev_technician else set()

        for project in core['technical_project']:
            project_id = project['id']
            company_id = project['owner_company_id']
            admin_id = self.company_admin[company_id]
            segment = self.units_by_company[company_id]['segment']
            address = addresses[units[project['local_unit_id']]['address_id']]
            trade_name = companies[company_id]['trade_name']
            rows = sorted(services.get(project_id, []), key=lambda row: row['scheduled_at'])
            status = project_status([row['status'] for row in rows])
            start = project['starts_at']
            kind = rng.choice(PROJECT_KINDS)
            ends = [row['ends_at'] for row in rows if row['ends_at']]
            project.update({
                'name': f"{kind} - {trade_name} ({address['city']})"[:160],
                'description': (f"{kind} na unidade de {segment} em {address['city']}/{address['state']}. "
                                f"{rng.choice(PROJECT_SCOPES)}"),
                'status': status,
                'ends_at': max(ends) if status == 'COMPLETED' and ends else None,
                'created_by_user_id': admin_id,
                'is_archived': status == 'COMPLETED' and rng.random() < 0.25,
                'created_at': start,
                'location_state': address['state'], 'location_city': address['city'],
                'location_neighborhood': address['neighborhood'], 'location_zip_code': address['zip_code'],
                'location_street': address['street'], 'location_number': address['number'],
                'location_complement': None,
            })

            members = {admin_id: ('MANAGER', 'Responsável')}
            staff = {**self.company_staff.get(company_id, {})}
            staff.update({position: user for position, user in self.dev_users.get(company_id, {}).items()
                          if position in ('MANAGER', 'SUPPORT')})
            if 'MANAGER' in staff:
                members.setdefault(staff['MANAGER'], ('MEMBER', 'Gerência'))
            if 'SUPPORT' in staff:
                members.setdefault(staff['SUPPORT'], ('VIEWER', 'Acompanhamento'))
            for row in rows:
                for executor in executors.get(row['id'], []):
                    user_id = affiliation_user.get(executor['technician_affiliation_id'])
                    if user_id:
                        members.setdefault(user_id, ('MEMBER', executor['function']))
            if project_id in dev_projects:
                members.setdefault(dev_technician, ('MEMBER', 'Técnico de campo'))
            for user_id, (role, function) in members.items():
                self.add('project_member', {
                    'id': uid('project_member', project_id, user_id), 'technical_project_id': project_id, 'user_id': user_id,
                    'role': role, 'function_name': function, 'is_active': True, 'joined_at': start,
                })

            self.add('project_history', {
                'id': uid('project_history', project_id, 'created'), 'technical_project_id': project_id, 'actor_user_id': admin_id,
                'action': 'CREATED', 'detail': 'Projeto criado', 'created_at': start,
            })
            self.add('project_activity', {
                'id': uid('project_activity', project_id, 'kickoff'), 'technical_project_id': project_id,
                'title': 'Reunião de alinhamento do projeto', 'description': 'Alinhamento de escopo, prazos e responsáveis.',
                'type': 'MEETING', 'status': 'COMPLETED', 'starts_at': start + timedelta(days=1),
                'ends_at': start + timedelta(days=1, hours=1), 'is_onsite': False,
                'assignee_user_ids': '{' + str(admin_id) + '}', 'technical_service_id': None,
            })
            for row in rows:
                assignees = [affiliation_user[e['technician_affiliation_id']] for e in executors.get(row['id'], [])
                             if e['technician_affiliation_id'] in affiliation_user]
                self.add('project_activity', {
                    'id': uid('project_activity', row['id']), 'technical_project_id': project_id, 'title': row['purpose'][:160],
                    'description': None, 'type': 'SERVICE', 'status': row['status'], 'starts_at': row['scheduled_at'],
                    # o banco exige ends_at > starts_at; no plano o fim do servico pode cair antes do agendamento
                    'ends_at': max(row['ends_at'], row['scheduled_at'] + timedelta(hours=2)) if row['ends_at'] else None,
                    'is_onsite': True, 'assignee_user_ids': '{' + ','.join(str(a) for a in assignees) + '}',
                    'technical_service_id': row['id'],
                })
                if row['status'] != 'OPEN':
                    self.add('project_history', {
                        'id': uid('project_history', row['id']), 'technical_project_id': project_id, 'actor_user_id': admin_id,
                        'action': 'ACTIVITY_STATUS', 'detail': f"{row['purpose'][:120]} → {row['status']}",
                        'created_at': row['ends_at'] or row['scheduled_at'],
                    })
            if status != 'OPEN':
                self.add('project_history', {
                    'id': uid('project_history', project_id, 'status'), 'technical_project_id': project_id, 'actor_user_id': admin_id,
                    'action': 'STATUS', 'detail': f'OPEN → {status}', 'created_at': start + timedelta(days=2),
                })
            self.project_photos(rng, project_id, admin_id, segment, start)

    def project_photos(self, rng, project_id, admin_id, segment, start):
        """Capa do local (galeria da unidade do mesmo ramo) mais fotos de obra; bytes JPEG no próprio banco."""
        site = self.pool.repeat_any([f'units/{segment}/{kind}' for kind in SITE_PHOTO_KINDS], rng)
        chosen = [site] + [self.pool.repeat_any(WORK_PHOTO_CATEGORIES, rng) for _ in range(rng.choice([1, 2, 2]))]
        seen = set()
        position = 0
        for image in chosen:
            if not image or image in seen:
                continue
            content = self.pool.jpeg_bytes(image)
            if content is None:
                continue
            seen.add(image)
            position += 1
            cover = position == 1
            created = start + timedelta(days=3 + position)
            self.add('project_photo', {
                'id': uid('project_photo', project_id, image), 'technical_project_id': project_id, 'name': f'foto-{position:02d}.jpg',
                'mime': 'image/jpeg', 'content': content, 'is_primary': cover, 'uploaded_by_user_id': admin_id, 'created_at': created,
            })
            self.add('project_history', {
                'id': uid('project_history', project_id, image), 'technical_project_id': project_id, 'actor_user_id': admin_id,
                'action': 'COVER_CHANGED' if cover else 'PHOTO_ADDED', 'detail': 'Capa atualizada' if cover else 'Foto adicionada',
                'created_at': created,
            })

    # ---------- catalog ----------
    def brand(self, name, owner_company_id=None):
        brand_id = uid('brand', name)
        self.add('brand', {
            'id': brand_id, 'owner_company_id': owner_company_id, 'name': name, 'normalized_name': name.lower(),
            'visibility': 'PUBLIC', 'is_archived': False, 'is_legacy': False, 'logo_url': None, 'reference_url': None,
        })
        return brand_id

    def photos_for_model(self, key, model_id, primary_pool, gallery_pool, gallery_count, unique):
        picker = (lambda cat: self.pool.unique(cat)) if unique else (lambda cat: self.pool.repeat(cat, self.rng))
        primary = picker(primary_pool)
        if primary:
            self.add('model_photo', {
                'id': uid('model_photo', key, 'primary'), 'model_id': model_id, 'url': self.pool.url(primary),
                'public_id': self.pool.public_id(primary), 'is_primary': True, 'created_at': self.when(-20),
            })
        if unique:
            gallery = [g for g in (self.pool.unique(gallery_pool) for _ in range(gallery_count)) if g]
        else:
            gallery = self.pool.sample(gallery_pool, gallery_count, self.rng)
        for position, image in enumerate(gallery):
            self.add('model_photo', {
                'id': uid('model_photo', key, 'gallery', position), 'model_id': model_id, 'url': self.pool.url(image),
                'public_id': self.pool.public_id(image), 'is_primary': False, 'created_at': self.when(-20, hours=position),
            })

    def build_catalog(self):
        panels = self.plan['panels']
        brands = [(name, self.brand(name)) for name in self.plan['brands']]
        edge = panels['edge']
        specs = []
        for family in panels['families']:
            specs.extend([family] * family['count'])
        statuses = (['UNDER_ANALYSIS'] * edge['under_analysis_models'] + ['REJECTED'] * edge['rejected_models'])
        status_slots = set(self.rng.sample(range(len(specs)), len(statuses)))
        status_iter = iter(statuses)
        models = []
        for index, family in enumerate(specs):
            brand_name, brand_id = brands[index % len(brands)]
            power = self.rng.randrange(family['power'][0], family['power'][1] + 1, 5)
            letter = {'MONOCRYSTALLINE': 'M', 'POLYCRYSTALLINE': 'P', 'THIN_FILM': 'F'}[family['type']]
            name = f'{brand_name[:2].upper()}-{power}{letter}{index:02d}'
            width = round(self.rng.uniform(0.99, 1.16), 3)
            area = self.rng.uniform(*family['area'])
            model_id = uid('model', name)
            status = next(status_iter) if index in status_slots else 'APPROVED'
            creator = self.rng.choice(self.suppliers)['company_id']
            self.add('model', {
                'id': model_id, 'brand_id': brand_id, 'model_name': name, 'power_wp': power,
                'efficiency': round(self.rng.uniform(*family['efficiency']), 1), 'dimension': None, 'type': family['type'],
                'width': width, 'length': round(area / width, 3), 'weight': round(self.rng.uniform(*family['weight']), 1),
                'status': status, 'product_type': 'PANEL', 'infrastructure_type': None, 'material': None,
                'creator_company_id': creator,
            })
            self.photos_for_model(name, model_id, 'products/solar-panels/hero', 'products/solar-panels/demo', 3, unique=False)
            models.append({'id': model_id, 'name': name, 'brand': brand_name, 'power': power, 'type': family['type']})
        self.panel_models = models
        self.build_panel_offers(models, panels)
        self.build_infrastructure()

    def offer_row(self, supplier, model_id, title, description, price, availability, slug, expired=False, paused=False, no_stock=False):
        offer_id = uid('offer', supplier['key'], slug)
        self.add('offer', {
            'id': offer_id, 'supplier_id': supplier['supplier_id'], 'model_id': model_id, 'unit_price': price,
            'availability': availability, 'expires_at': self.when(-5) if expired else self.when(self.rng.randint(60, 400)),
            'slug': f'{supplier["key"]}-{slug}'[:160],
            'discount_percentage': self.rng.choice([None, None, 3, 5, 8, 10, 15]), 'source_locale': 'pt-BR',
            'translation_status': 'COMPLETED', 'commercial_status': 'PAUSED' if paused else 'ACTIVE',
        })
        self.add('inventory', {
            'id': uid('inventory', supplier['key'], slug), 'supplier_id': supplier['supplier_id'], 'model_id': model_id,
            'quantity': 0 if no_stock else int(availability * self.rng.uniform(1.0, 2.0)),
        })
        for locale, (loc_title, loc_description) in {
            'pt-BR': (title, description),
            'en-US': (title, f'Offer {title} from {supplier["name"]}. Seeded sample data.'),
            'es-ES': (title, f'Oferta {title} de {supplier["name"]}. Datos de ejemplo.'),
        }.items():
            self.add('offer_translation', {
                'id': uid('offer_translation', offer_id, locale), 'offer_id': offer_id, 'locale': locale,
                'title': loc_title[:160], 'description': loc_description, 'details': None,
            })
        self.offers.append({'id': offer_id, 'supplier_key': supplier['key'], 'supplier_id': supplier['supplier_id'], 'price': price, 'paused': paused,
                            'expired': expired, 'kind': 'panel' if not title.startswith('Infra') else 'infra'})
        return offer_id

    def build_panel_offers(self, models, panels):
        edge = panels['edge']
        total = panels['offers']
        per_supplier = [total // len(self.suppliers) + (1 if index < total % len(self.suppliers) else 0)
                        for index in range(len(self.suppliers))]
        low, high = panels['price_per_wp']
        for supplier, count in zip(self.suppliers, per_supplier):
            chosen = self.rng.sample(models, count)
            for model in chosen:
                price_wp = self.rng.uniform(low, high) * supplier['price_factor']
                price = round(model['power'] * price_wp, 2)
                self.offer_row(
                    supplier, model['id'], f'Painel {model["brand"]} {model["name"]} {model["power"]}W',
                    f'Painel solar {model["type"].lower().replace("_", " ")} de {model["power"]} Wp da {model["brand"]}.',
                    price, self.rng.randint(20, 600), slugify(model['name']),
                    expired=self.rng.random() < edge['expired_offer_ratio'],
                    paused=self.rng.random() < edge['paused_offer_ratio'],
                    no_stock=self.rng.random() < edge['no_stock_ratio'],
                )

    def build_infrastructure(self):
        infra = self.plan['infrastructure']
        infra_brands = {name: self.brand(name) for name in self.plan['infra_brands']}
        sellers = [s for s in self.suppliers if s['subscription'] == 'paid']
        for index, product in enumerate(infra['products']):
            model_id = uid('model', 'infra', product['name'])
            self.add('model', {
                'id': model_id, 'brand_id': infra_brands[product['brand']], 'model_name': product['name'], 'power_wp': None,
                'efficiency': None, 'dimension': None, 'type': None, 'width': None, 'length': None, 'weight': None,
                'status': 'APPROVED', 'product_type': 'INFRASTRUCTURE', 'infrastructure_type': product['type'],
                'material': product['material'], 'creator_company_id': self.rng.choice(sellers)['company_id'],
            })
            self.photos_for_model(f'infra:{product["name"]}', model_id, 'products/infrastructure/hero',
                                  'products/infrastructure/gallery', 2, unique=True)
            for offset in range(infra['offers_per_product']):
                supplier = sellers[(index + offset) % len(sellers)]
                price = round(product['price'] * supplier['price_factor'], 2)
                self.offer_row(supplier, model_id, f'Infra {product["name"]}', f'{product["name"]} em {product["material"].lower()}.',
                               price, self.rng.randint(80, 2500), slugify(product['name']))

    # ---------- technicians ----------
    def build_technicians(self):
        plan = self.plan['technicians']
        professions = []
        for name, count in plan['professions'].items():
            professions.extend([name] * count)
        assert len(professions) == plan['count'], 'plan.technicians.count deve bater com a soma das profissoes'
        self.rng.shuffle(professions)
        cert_names = read_catalog('certification_name', 'name')
        cert_descriptions = read_catalog('certification_description', 'description')
        statuses = ['APPROVED'] * (plan['count'] - 4) + ['UNDER_ANALYSIS'] * 3 + ['REJECTED']
        self.rng.shuffle(statuses)
        self.technicians = []
        for index, profession in enumerate(professions):
            company = self.technical_companies[index % len(self.technical_companies)]
            key = f'technician:{index}'
            user_id, person_id, name = self.user(key, 'users/pfp/professionals', company['company_id'], 'TECHNICIAN')
            technician_id = uid('technician', index)
            council = self.rng.choice(COUNCILS)
            number = str(self.rng.randint(100000, 999999))
            self.add('technician', {
                'id': technician_id, 'person_id': person_id, 'crea': f'{council} {number}',
                'slug': f'{slugify(name)}-{index}', 'status': statuses[index],
            })
            registration_id = uid('registration', index)
            expired = self.rng.random() < plan['expired_registration_ratio']
            self.add('professional_registration', {
                'id': registration_id, 'technician_id': technician_id, 'profession_id': Ref('profession', profession),
                'council': council, 'number': number,
                'expires_at': (self.when(-self.rng.randint(10, 300)) if expired else self.when(self.rng.randint(90, 900))),
            })
            if statuses[index] == 'APPROVED':
                self.approved_onboarding(user_id, technician_id, council, number, self.when(720))
            for cert_index in range(self.rng.choice([0, 1, 1, 2, 3])):
                cert_id = uid('certification', index, cert_index)
                cert_name = self.rng.choice(cert_names)
                self.add('certification', {
                    'id': cert_id, 'technician_id': technician_id, 'type': cert_name.split(' ')[0],
                    'information': self.rng.choice(cert_descriptions), 'image': None,
                    'description': self.rng.choice(cert_descriptions), 'issuer': 'Entidade certificadora ficticia',
                    'name': cert_name[:100],
                    'valid_until_at': self.when(self.rng.randint(-120, 700)),
                })
                self.add('certification_record', {
                    'id': uid('certification_record', index, cert_index), 'professional_registration_id': registration_id,
                    'certification_id': cert_id,
                })
            affiliation_id = uid('affiliation', index)
            self.add('technician_affiliation', {
                'id': affiliation_id, 'company_id': company['company_id'], 'technician_id': technician_id,
                'affiliation_type': self.rng.choices(['AFFILIATED', 'PARTNER', 'INDEPENDENT'], [60, 25, 15])[0], 'is_active': True,
            })
            self.technicians.append({'id': technician_id, 'affiliation': affiliation_id, 'user': user_id})

    # ---------- proposals ----------
    def build_proposals(self):
        plan = self.plan['proposals']
        sellable = [o for o in self.offers if o['kind'] == 'panel' and not o['paused'] and not o['expired']]
        companies = [c for c, info in self.units_by_company.items()]
        accepted = round(plan['count'] * plan['accepted_ratio'])
        statuses = ['ACCEPTED'] * accepted + ['AWAITING_SUPPLIER'] * 6 + ['AWAITING_REQUESTER'] * 3 + ['REJECTED'] * 2 + ['CANCELED'] * 1
        statuses = (statuses + ['AWAITING_SUPPLIER'] * plan['count'])[:plan['count']]
        for index, status in enumerate(statuses):
            company_id = self.rng.choice(companies)
            info = self.units_by_company[company_id]
            proposal_id = uid('proposal', index)
            supplier_id = self.rng.choice(sorted({o['supplier_id'] for o in sellable}))
            pool = [o for o in sellable if o['supplier_id'] == supplier_id]
            items = self.rng.sample(pool, min(len(pool), self.rng.randint(1, 3)))
            total = 0
            item_rows = []
            for item_index, offer in enumerate(items):
                quantity = self.rng.randint(len(info['units']), len(info['units']) * 12)
                discount = self.rng.choice([0, 0, 3, 5])
                negotiated = round(offer['price'] * (1 - discount / 100), 2) if status == 'ACCEPTED' else None
                total += quantity * (negotiated or offer['price'])
                item_id = uid('proposal_item', index, item_index)
                item_rows.append((item_id, quantity))
                self.add('proposal_item', {
                    'id': item_id, 'proposal_id': proposal_id, 'offer_id': offer['id'], 'quantity': quantity,
                    'negotiated_unit_price': negotiated, 'discount': discount if negotiated else None,
                })
            self.add('proposal', {
                'id': proposal_id, 'requester_id': info['requester'], 'supplier_id': supplier_id, 'status': status,
                'notes': 'Proposta gerada pelo seed planejado.', 'total_amount': round(total, 2),
                'created_at': self.when(-self.rng.randint(3, 160)), 'updated_at': None,
            })
            for item_id, quantity in item_rows:
                units = self.rng.sample(info['units'], min(len(info['units']), self.rng.randint(1, 3)))
                share = max(1, quantity // len(units))
                for unit_index, unit_id in enumerate(units):
                    self.add('proposal_unit', {
                        'id': uid('proposal_unit', item_id, unit_index), 'proposal_item_id': item_id,
                        'local_unit_id': unit_id, 'quantity': share, 'note': None,
                    })

    # ---------- orders ----------
    def build_orders(self):
        plan = self.plan.get('orders')
        if not plan:
            return
        # Gerador proprio: o sorteio dos pedidos nao desloca nenhum dado gerado depois.
        rng = random.Random(f"{self.plan['rng_seed']}:orders")
        cents = Decimal('0.01')
        offer_rows = {row['id']: row for row in self.data.core['offer']}
        model_names = {row['id']: row['model_name'] for row in self.data.core['model']}
        purchasable = [
            offer_rows[o['id']] for o in self.offers
            if not o['paused'] and not o['expired'] and offer_rows[o['id']]['availability'] > 0
        ]
        buyers = {
            'demandant': [self.company_admin[company_id] for company_id in self.units_by_company],
            'professional': [t['user'] for t in self.technicians],
        }
        taken = Counter()
        fee_percentage = Decimal(str(plan['fee_percentage']))

        supplier_by_company = {row['company_id']: row['id'] for row in self.data.core['supplier']}
        own_suppliers = {}
        for membership in self.data.core['user_company']:
            supplier_id = supplier_by_company.get(membership['company_id'])
            if supplier_id:
                own_suppliers.setdefault(membership['user_id'], set()).add(supplier_id)

        def lines(buyer_id, supplier_count, item_count):
            by_supplier = OrderedDict()
            for row in purchasable:
                if row['supplier_id'] not in own_suppliers.get(buyer_id, ()):
                    by_supplier.setdefault(row['supplier_id'], []).append(row)
            chosen = rng.sample(list(by_supplier), min(supplier_count, len(by_supplier)))
            pool = [row for supplier in chosen for row in by_supplier[supplier]]
            return rng.sample(pool, min(item_count, len(pool)))

        for index, spec in enumerate(plan['purchases']):
            kind = spec['buyer']
            buyer_id = buyers[kind][spec.get('buyer_index', index) % len(buyers[kind])]
            order_id = uid('purchase_order', index)
            created_at = self.when(spec['days'])
            subtotal = Decimal('0')
            for line_index, offer in enumerate(lines(buyer_id, spec['suppliers'], spec['items'])):
                quantity = rng.randint(1, min(3, offer['availability']))
                unit_price = Decimal(str(offer['unit_price'])).quantize(cents, ROUND_HALF_UP)
                discount = Decimal(str(offer['discount_percentage'] or 0))
                net = (unit_price * (100 - discount) / 100).quantize(cents, ROUND_HALF_UP)
                line_total = net * quantity
                subtotal += line_total
                self.add('order_item', {
                    'id': uid('order_item', index, line_index), 'purchase_order_id': order_id, 'offer_id': offer['id'],
                    'supplier_id': offer['supplier_id'], 'offer_slug': offer['slug'],
                    'model_name': model_names[offer['model_id']], 'unit_price': unit_price,
                    'discount_percentage': discount, 'net_unit_price': net, 'quantity': quantity, 'line_total_amount': line_total,
                })
                if spec['status'] == 'PAID':
                    taken[offer['id']] += quantity
            fee = (subtotal * fee_percentage).quantize(cents, ROUND_HALF_UP)
            canceled = spec['status'] == 'CANCELED'
            self.add('purchase_order', {
                'id': order_id, 'buyer_user_id': buyer_id, 'status': spec['status'], 'subtotal_amount': subtotal,
                'fee_percentage': fee_percentage, 'fee_amount': fee, 'total_amount': subtotal + fee, 'created_at': created_at,
                'canceled_at': created_at + timedelta(days=1) if canceled else None,
                'canceled_by_user_id': buyer_id if canceled else None,
            })
            self.add('order_payment', {
                'id': uid('order_payment', index), 'purchase_order_id': order_id, 'method': spec['method'], 'amount': subtotal + fee,
                'status': 'REFUNDED' if canceled else 'PAID', 'paid_at': created_at,
                'refunded_at': created_at + timedelta(days=1) if canceled else None,
            })
        for offer_id, quantity in taken.items():
            offer_rows[offer_id]['availability'] -= quantity
        for index, spec in enumerate(plan.get('carts', [])):
            kind = spec['buyer']
            buyer_id = buyers[kind][spec.get('buyer_index', index) % len(buyers[kind])]
            cart_id = uid('cart', index)
            self.add('cart', {'id': cart_id, 'user_id': buyer_id, 'created_at': self.when(-1), 'updated_at': self.when(-1)})
            for line_index, offer in enumerate(lines(buyer_id, spec['suppliers'], spec['items'])):
                self.add('cart_item', {
                    'id': uid('cart_item', index, line_index), 'cart_id': cart_id, 'offer_id': offer['id'],
                    'quantity': rng.randint(1, 2), 'added_at': self.when(-1),
                })

    # ---------- technical services ----------
    def build_services(self):
        plan = self.plan['services']
        purposes = read_catalog('technical_service_purpose', 'purpose')
        comments = read_catalog('review_comment', 'comment')
        weights = [1 / (position + 1) ** 0.8 for position in range(len(self.technicians))]
        order = list(range(len(self.technicians)))
        self.rng.shuffle(order)
        status_names = list(plan['status_weights'])
        status_weights = list(plan['status_weights'].values())
        review_counts = Counter()
        projects = {}
        company_ids = list(self.units_by_company)
        for index in range(plan['count']):
            company_id = self.rng.choice(company_ids)
            info = self.units_by_company[company_id]
            unit_id = self.rng.choice(info['units'])
            if unit_id not in projects:
                projects[unit_id] = uid('technical_project', unit_id)
                self.add('technical_project', {
                    'id': projects[unit_id], 'requester_id': info['requester'], 'local_unit_id': unit_id, 'owner_company_id': company_id,
                    'status': 'OPEN', 'starts_at': self.when(-self.rng.randint(30, 300)), 'ends_at': None,
                })
            status = self.rng.choices(status_names, status_weights)[0]
            created = self.when(-self.rng.randint(5, 240))
            service_id = uid('service', index)
            self.add('technical_service', {
                'id': service_id, 'technical_project_id': projects[unit_id], 'purpose': self.rng.choice(purposes)[:255],
                'status': status, 'scheduled_at': created + timedelta(days=self.rng.randint(2, 30)), 'created_at': created,
                'accepted_by_user_id': None, 'accepted_at': None,
                'ends_at': created + timedelta(days=self.rng.randint(3, 40)) if status == 'COMPLETED' else None,
            })
            executors = {order[self.rng.choices(range(len(order)), weights)[0]] for _ in range(self.rng.randint(1, 2))}
            for position, technician_index in enumerate(sorted(executors)):
                technician = self.technicians[technician_index]
                self.add('service_executor', {
                    'id': uid('executor', index, position), 'technical_service_id': service_id,
                    'technician_affiliation_id': technician['affiliation'],
                    'function': 'Responsavel tecnico' if position == 0 else 'Auxiliar de instalacao',
                })
                if status == 'COMPLETED' and review_counts[technician_index] < self.plan['technicians']['max_reviews'] and self.rng.random() < 0.8:
                    review_counts[technician_index] += 1
                    rating = self.rng.choices([5.0, 4.5, 4.0, 3.5, 3.0, 2.0], [34, 24, 20, 10, 8, 4])[0]
                    self.add('professional_review', {
                        'id': uid('review', index, position), 'technician_id': technician['id'],
                        'reviewer_user_id': self.company_admin[company_id], 'technical_service_id': service_id, 'rating': rating,
                        'comment': self.rng.choice(comments)[:255], 'is_active': True, 'created_at': created + timedelta(days=20),
                    })


PROJECT_KINDS = ['Usina solar', 'Projeto fotovoltaico', 'Instalação de painéis', 'Modernização solar']
PROJECT_SCOPES = [
    'Vistoria técnica, dimensionamento, instalação dos módulos e inversores e comissionamento com entrega documentada.',
    'Levantamento de carga, projeto elétrico, instalação em cobertura e homologação junto à concessionária.',
    'Estudo de viabilidade, instalação do sistema fotovoltaico, adequação do quadro elétrico e treinamento da equipe.',
]
SITE_PHOTO_KINDS = ('gallery', 'main', 'banner')
WORK_PHOTO_CATEGORIES = ['enterprises/banners/solar', 'enterprises/banners/construction']


def project_status(statuses):
    """Situação do projeto a partir dos serviços: em andamento se algum está, concluído/cancelado se todos estão."""
    if 'IN_PROGRESS' in statuses:
        return 'IN_PROGRESS'
    if statuses and all(status == 'COMPLETED' for status in statuses):
        return 'COMPLETED'
    if statuses and all(status == 'CANCELED' for status in statuses):
        return 'CANCELED'
    return 'OPEN'


def build_dataset(plan, pool, today):
    return Builder(plan, pool, today).build()
