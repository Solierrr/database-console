import json
from decimal import Decimal
import os
import re
import tempfile
import unittest
import uuid
from collections import Counter
from datetime import date
from pathlib import Path

import psycopg2
from psycopg2 import sql

from seed.builder import CORE_TABLES, Ref, build_dataset
from seed.images import ImagePool
from seed.loader import load_dataset, load_plan

ROOT = Path(__file__).resolve().parents[1]
PLAN = load_plan(ROOT / 'seed' / 'plan.yaml')
TODAY = date(2026, 10, 11)


def synthetic_manifest(directory, size=60):
    categories = (
        ['users/pfp/suitman', 'users/pfp/professionals', 'users/pfp/staff', 'users/pfp/clients',
         'users/banners/landscapes', 'users/banners/colors', 'users/banners/abstract', 'enterprises/pfp',
         'products/solar-panels/hero', 'products/solar-panels/demo', 'products/infrastructure/hero',
         'products/infrastructure/gallery']
        + [f'enterprises/banners/{theme}' for theme in ('corporate', 'construction', 'industrial', 'hospitality', 'retail', 'solar')]
        + [f'units/{entry["segment"]}/{kind}' for entry in PLAN['demandants'] for kind in ('main', 'banner', 'gallery')]
    )
    assets = [
        {'id': f'{category.replace("/", "-")}-{index:03d}', 'category': category}
        for category in categories for index in range(size)
    ]
    path = Path(directory) / 'manifest.json'
    path.write_text(json.dumps({'version': 1, 'assets': assets}), encoding='utf-8')
    return path


def build(directory, cloud='test-cloud'):
    pool = ImagePool(synthetic_manifest(directory), PLAN['rng_seed'], cloud)
    return build_dataset(PLAN, pool, TODAY), pool


class SeedPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.data, cls.pool = build(cls.directory.name)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_build_is_deterministic(self):
        other, _ = build(self.directory.name)
        self.assertEqual(repr(self.data.core), repr(other.core))
        self.assertEqual(repr(self.data.auth), repr(other.auth))

    def test_volumes_match_the_approved_plan(self):
        counts = self.data.counts()
        self.assertEqual(15, counts['requester'])
        self.assertEqual(64, counts['local_unit'])
        self.assertEqual(40 + 2, counts['technician'])  # plano + dev_tec_technician + conta única teste
        self.assertEqual(8, len({row['profession_id'].name for row in self.data.core['professional_registration']}))
        self.assertEqual(30, counts['proposal'])
        self.assertEqual(150, counts['technical_service'])
        self.assertEqual(counts['user_account'], counts['auth_user'])
        units_by_requester = Counter(row['requester_id'] for row in self.data.core['local_unit'])
        self.assertEqual(10, max(units_by_requester.values()))

    def test_single_test_account_has_all_development_contexts(self):
        auth = next(row for row in self.data.auth['auth_user'] if row['primary_email'] == 'teste@teste')
        user = next(row for row in self.data.core['user_account'] if row['auth_id'] == auth['id'])
        self.assertIsNone(user['managed_by_company_id'])
        memberships = [row for row in self.data.core['user_company'] if row['user_id'] == user['id']]
        self.assertEqual(3, len(memberships))
        self.assertTrue(all(row['job_position_id'].name == 'ADMIN' for row in memberships))
        self.assertTrue(any(row['user_id'] == user['id'] for row in self.data.core['platform_admin']))
        person = next(row for row in self.data.core['person'] if row['user_id'] == user['id'])
        self.assertTrue(any(row['person_id'] == person['id'] for row in self.data.core['technician']))
        members = [row for row in self.data.core['project_member'] if row['user_id'] == user['id']]
        self.assertEqual(len(self.data.core['technical_project']), len(members))
        self.assertTrue(all(row['is_active'] and row['role'] == 'MANAGER' for row in members))
        credential = next(row for row in self.data.auth['local_credential'] if row['auth_user_id'] == auth['id'])
        self.assertEqual(PLAN['dev_test_account']['password_hash'], credential['password_hash'])

    def test_panel_and_infrastructure_rows_respect_product_rules(self):
        models = self.data.core['model']
        panels = [m for m in models if m['product_type'] == 'PANEL']
        infra = [m for m in models if m['product_type'] == 'INFRASTRUCTURE']
        self.assertEqual(45, len(panels))
        self.assertEqual(6, len(infra))
        for model in panels:
            self.assertTrue(all(model[c] is not None for c in ('power_wp', 'efficiency', 'type', 'width', 'length', 'weight')))
            self.assertIsNone(model['infrastructure_type'])
        for model in infra:
            self.assertIsNotNone(model['infrastructure_type'])
            self.assertTrue(all(model[c] is None for c in ('power_wp', 'efficiency', 'type')))
        self.assertEqual({'APPROVED', 'UNDER_ANALYSIS', 'REJECTED'}, {m['status'] for m in panels})

    def test_edge_cases_exist_for_recommendation_filters(self):
        offers = self.data.core['offer']
        self.assertTrue(any(o['commercial_status'] == 'PAUSED' for o in offers))
        self.assertTrue(any(o['expires_at'] < self.today_start() for o in offers))
        self.assertTrue(any(i['quantity'] == 0 for i in self.data.core['inventory']))
        statuses = Counter(s['status'] for s in self.data.core['subscription'])
        self.assertEqual(1, statuses['IN_DEBT'])
        self.assertEqual({'APPROVED', 'UNDER_ANALYSIS', 'REJECTED'}, {c['status'] for c in self.data.core['company']})

    def today_start(self):
        from datetime import datetime, time, timezone
        return datetime.combine(TODAY, time(12, 0), tzinfo=timezone.utc)

    def test_users_have_unique_photos_and_valid_identifiers(self):
        avatars = [u['avatar'] for u in self.data.core['user_account'] if u['avatar']]
        self.assertEqual(len(avatars), len(set(avatars)))
        usernames = [u['username'] for u in self.data.core['user_account']]
        self.assertEqual(len(usernames), len(set(usernames)))
        for username in usernames:
            self.assertRegex(username, r'^[a-z0-9_]{3,30}$')
        for company in self.data.core['company']:
            self.assertEqual(14, len(company['cnpj']))
        for person in self.data.core['person']:
            self.assertEqual(11, len(person['cpf']))
        self.assertFalse({u['auth_id'] for u in self.data.core['user_account']} - {a['id'] for a in self.data.auth['auth_user']})

    def test_company_logo_banner_and_unit_main_banner_are_never_repeated(self):
        company_images = [(p['type'], p['public_id']) for p in self.data.core['company_photo']]
        self.assertEqual(len(company_images), len(set(company_images)))
        logos = [p['public_id'] for p in self.data.core['company_photo'] if p['type'] == 'PROFILE']
        banners = [p['public_id'] for p in self.data.core['company_photo'] if p['type'] == 'BANNER']
        self.assertEqual(len(logos), len(set(logos)))
        self.assertEqual(len(banners), len(set(banners)))
        primaries = [p for p in self.data.core['local_unit_photo'] if p['is_primary']]
        banners = [p for p in self.data.core['local_unit_photo'] if p['type'] == 'BANNER']
        for kind, photos in (('primary', primaries), ('banner', banners)):
            used = [p['public_id'] for p in photos]
            self.assertEqual(len(used), len(set(used)), kind)
        self.assertTrue(all(p['type'] == 'GALLERY' for p in primaries))
        per_unit = Counter(p['local_unit_id'] for p in primaries)
        self.assertTrue(all(count == 1 for count in per_unit.values()))
        per_unit = Counter(p['local_unit_id'] for p in banners)
        self.assertTrue(all(count == 1 for count in per_unit.values()))

    def test_infrastructure_images_are_unique_and_panel_images_may_repeat(self):
        infra_ids = {m['id'] for m in self.data.core['model'] if m['product_type'] == 'INFRASTRUCTURE'}
        infra_images = [p['public_id'] for p in self.data.core['model_photo'] if p['model_id'] in infra_ids]
        self.assertEqual(len(infra_images), len(set(infra_images)))
        primaries = Counter(p['model_id'] for p in self.data.core['model_photo'] if p['is_primary'])
        self.assertTrue(all(count == 1 for count in primaries.values()))

    def test_unit_segment_images_come_from_the_matching_segment(self):
        segments = {}
        for entry in PLAN['demandants']:
            segments[entry['key']] = entry['segment']
        by_unit = {}
        for requester in self.data.core['requester']:
            by_unit[requester['id']] = requester['business_type']
        unit_owner = {u['id']: by_unit[u['requester_id']] for u in self.data.core['local_unit']}
        for photo in self.data.core['local_unit_photo']:
            segment = unit_owner[photo['local_unit_id']]
            self.assertIn(f'units-{segment}-', photo['public_id'])

    def test_references_point_to_existing_rows_or_known_catalog_entries(self):
        ids = {table: {row['id'] for row in rows if 'id' in row} for table, rows in self.data.core.items()}
        links = {
            'address_id': 'address', 'business_contact_id': 'business_contact', 'company_id': 'company', 'user_id': 'user_account',
            'person_id': 'person', 'user_id': 'user_account', 'supplier_id': 'supplier', 'brand_id': 'brand', 'model_id': 'model',
            'offer_id': 'offer', 'requester_id': 'requester', 'local_unit_id': 'local_unit', 'proposal_id': 'proposal',
            'proposal_item_id': 'proposal_item', 'technician_id': 'technician', 'technician_id': 'technician',
            'technical_project_id': 'technical_project', 'technical_service_id': 'technical_service', 'reviewer_user_id': 'user_account',
            'professional_registration_id': 'professional_registration', 'certification_id': 'certification',
            'technician_affiliation_id': 'technician_affiliation', 'creator_company_id': 'company', 'owner_company_id': 'company',
            'cart_id': 'cart', 'purchase_order_id': 'purchase_order', 'buyer_user_id': 'user_account',
        }
        for table, rows in self.data.core.items():
            for row in rows:
                for column, value in row.items():
                    if value is None:
                        continue
                    if isinstance(value, Ref):
                        self.assertIn(value.table, ('job_position', 'profession', 'company_plan', 'permission'))
                        continue
                    if column not in links:
                        continue
                    self.assertIn(value, ids[links[column]], f'{table}.{column}')

    def test_orders_are_consistent_and_respect_who_can_buy(self):
        orders = self.data.core['purchase_order']
        items = self.data.core['order_item']
        payments = {row['purchase_order_id']: row for row in self.data.core['order_payment']}
        supplier_by_company = {row['company_id']: row['id'] for row in self.data.core['supplier']}
        own = {}
        for row in self.data.core['user_company']:
            if row['company_id'] in supplier_by_company:
                own.setdefault(row['user_id'], set()).add(supplier_by_company[row['company_id']])
        professionals = {
            person['user_id'] for person in self.data.core['person']
            if any(t['person_id'] == person['id'] and t['status'] == 'APPROVED' for t in self.data.core['technician'])
        }
        self.assertEqual(len(PLAN['orders']['purchases']), len(orders))
        self.assertEqual({'PAID', 'CANCELED'}, {order['status'] for order in orders})
        self.assertTrue(self.data.core['cart'] and self.data.core['cart_item'])
        for order in orders:
            self.assertTrue(order['buyer_user_id'] not in own or order['buyer_user_id'] in professionals)
            lines = [row for row in items if row['purchase_order_id'] == order['id']]
            self.assertTrue(lines)
            for line in lines:
                self.assertNotIn(line['supplier_id'], own.get(order['buyer_user_id'], set()))
            self.assertEqual(order['subtotal_amount'], sum(line['line_total_amount'] for line in lines))
            self.assertEqual(order['total_amount'], order['subtotal_amount'] + order['fee_amount'])
            self.assertEqual(Decimal('0.005'), order['fee_percentage'])
            self.assertEqual(order['total_amount'], payments[order['id']]['amount'])
            self.assertEqual('REFUNDED' if order['status'] == 'CANCELED' else 'PAID', payments[order['id']]['status'])
        for line in items:
            self.assertEqual(line['line_total_amount'], line['net_unit_price'] * line['quantity'])
        for cart in self.data.core['cart']:
            self.assertTrue(cart['user_id'] not in own or cart['user_id'] in professionals)
        self.assertTrue(all(row['availability'] >= 0 for row in self.data.core['offer']))

    def test_image_report_has_no_shortage_with_a_large_enough_pool(self):
        self.assertEqual([], [row for row in self.data.image_report if row[3]])

    def test_urls_use_the_cloud_prefix_and_public_id_convention(self):
        photo = self.data.core['user_photo'][0]
        self.assertTrue(photo['url'].startswith('https://res.cloudinary.com/test-cloud/image/upload/mocks/'))
        self.assertTrue(photo['public_id'].startswith('mocks/'))
        self.assertTrue(photo['url'].endswith(photo['public_id'].split('/', 1)[1] + '.webp'))

    def test_real_manifest_crops_flow_into_photo_rows_all_or_nothing(self):
        pool = ImagePool(ROOT.parent / 'mocks-warehouse' / 'manifest.json', PLAN['rng_seed'], 'x')
        data = build_dataset(PLAN, pool, TODAY)
        columns = ('crop_x', 'crop_y', 'crop_width', 'crop_height')
        with_crop = [row for row in data.core['user_photo'] if row['crop_x'] is not None]
        self.assertTrue(with_crop)
        for row in with_crop:
            self.assertTrue(all(isinstance(row[column], int) for column in columns))
            self.assertGreater(row['crop_width'], 0)
        for row in data.core['user_photo'] + data.core['company_photo']:
            self.assertIn(sum(row[column] is not None for column in columns), (0, 4))
        for table in ('user_photo', 'company_photo'):
            self.assertEqual(1, len({tuple(sorted(row)) for row in data.core[table]}))

    def test_dev_accounts_cover_every_position_with_fixed_logins(self):
        pool = ImagePool(ROOT.parent / 'mocks-warehouse' / 'manifest.json', PLAN['rng_seed'], 'x')
        data = build_dataset(PLAN, pool, TODAY)
        usernames = {row['username']: row['id'] for row in data.core['user_account']}
        expected = {username: position for group in PLAN['dev_accounts'] for username, position in group['accounts']}
        self.assertEqual(10, len(expected))
        links = {row['user_id']: row['job_position_id'] for row in data.core['user_company']}
        for username, position in expected.items():
            self.assertIn(username, usernames)
            self.assertEqual(Ref('job_position', position), links[usernames[username]])
        self.assertEqual({'ADMIN', 'MANAGER', 'SALES', 'SUPPORT', 'TECHNICIAN'}, set(expected.values()))
        self.assertIn(usernames[PLAN['dev_platform_admin']], {row['user_id'] for row in data.core['platform_admin']})
        emails = {row['primary_email'] for row in data.auth['auth_user']}
        self.assertTrue(all(f'{name}@solaria.dev' in emails for name in expected))
        self.assertEqual(len(usernames), len(data.core['user_account']))

    def test_approved_technicians_have_an_approved_onboarding_profile(self):
        approved = {row['id']: row for row in self.data.core['technician'] if row['status'] == 'APPROVED'}
        profiles = {row['technician_id']: row for row in self.data.core['professional_onboarding']}
        self.assertEqual(set(approved), set(profiles))
        users = {row['id']: row for row in self.data.core['user_account']}
        persons = {row['id']: row for row in self.data.core['person']}
        for technician_id, profile in profiles.items():
            self.assertEqual(1, profile['approved_version'])
            self.assertFalse(profile['is_suspended'])
            self.assertIsNotNone(profile['approved_json'])
            self.assertEqual(profile['auth_id'], users[profile['user_id']]['auth_id'])
            self.assertEqual(persons[approved[technician_id]['person_id']]['user_id'], profile['user_id'])
        self.assertEqual(len(profiles), len({row['auth_id'] for row in profiles.values()}))

    def test_seed_accounts_use_the_simple_domain_and_password(self):
        emails = {row['primary_email'] for row in self.data.auth['auth_user']}
        self.assertTrue(all(email.endswith('@solaria.dev') for email in emails if not email.startswith('teste@')))
        hashes = {row['password_hash'] for row in self.data.auth['local_credential']}
        self.assertEqual({PLAN['auth']['password_hash'], PLAN['dev_test_account']['password_hash']}, hashes)

    def test_default_position_permissions_skip_admin_and_stay_least_privilege(self):
        granted = PLAN['position_permissions']
        self.assertNotIn('ADMIN', granted)
        for position, names in granted.items():
            self.assertEqual(len(names), len(set(names)), position)
        # menor privilegio: so ADMIN governa cargos/permissoes; leitura-apenas nao escreve
        forbidden = ('/api/position-permissions', '/api/positions', '/api/permissions')
        for names in granted.values():
            self.assertFalse([n for n in names if n.split(' ', 1)[1].startswith(forbidden)])
        for position in ('SUPPORT', 'TECHNICIAN'):
            self.assertTrue(all(name.startswith('GET ') for name in granted[position]), position)
        self.assertEqual(sum(len(v) for v in granted.values()), len(self.data.core['position_permission']))

    def test_projects_have_names_members_activities_and_cover_photos(self):
        pool = ImagePool(ROOT.parent / 'mocks-warehouse' / 'manifest.json', PLAN['rng_seed'], 'x')
        data = build_dataset(PLAN, pool, TODAY)
        projects = data.core['technical_project']
        self.assertGreater(len(projects), 40)
        members, photos, activities = {}, {}, {}
        for row in data.core['project_member']:
            members.setdefault(row['technical_project_id'], []).append(row)
        for row in data.core['project_photo']:
            photos.setdefault(row['technical_project_id'], []).append(row)
        for row in data.core['project_activity']:
            activities.setdefault(row['technical_project_id'], []).append(row)
        services = Counter(row['technical_project_id'] for row in data.core['technical_service'])
        self.assertEqual({p['id'] for p in projects}, set(services), 'todo projeto tem ao menos um servico e vice-versa')
        self.assertGreater(len({row['name'] for row in projects}), 20)
        for project in projects:
            pid = project['id']
            self.assertNotEqual('Projeto técnico', project['name'])
            self.assertTrue(project['description'])
            self.assertEqual(2, len(project['location_state']))
            self.assertIn(project['status'], {'OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELED'})
            roles = {(m['user_id'], m['role']) for m in members[pid]}
            self.assertIn((project['created_by_user_id'], 'MANAGER'), roles)
            self.assertEqual(len(members[pid]), len({m['user_id'] for m in members[pid]}))
            self.assertEqual(services[pid] + 1, len(activities[pid]))
            for activity in activities[pid]:
                self.assertTrue(activity['ends_at'] is None or activity['ends_at'] > activity['starts_at'])
            covers = [p for p in photos[pid] if p['is_primary']]
            self.assertEqual(1, len(covers), 'cada projeto tem exatamente uma capa')
            for photo in photos[pid]:
                self.assertEqual('image/jpeg', photo['mime'])
                self.assertEqual(bytes([0xFF, 0xD8, 0xFF]), photo['content'][:3])
                self.assertLess(len(photo['content']), 8 * 1024 * 1024)
            if project['status'] == 'COMPLETED':
                self.assertIsNotNone(project['ends_at'])
        self.assertGreaterEqual({p['status'] for p in projects}, {'IN_PROGRESS', 'COMPLETED', 'OPEN'})

    def test_dev_accounts_can_see_the_projects_of_their_company(self):
        pool = ImagePool(ROOT.parent / 'mocks-warehouse' / 'manifest.json', PLAN['rng_seed'], 'x')
        data = build_dataset(PLAN, pool, TODAY)
        users = {row['username']: row['id'] for row in data.core['user_account']}
        aurora = uuid.uuid5(uuid.UUID('6f1c1b2e-5d3a-4f7e-9a41-0c2d8b7e5a10'), 'company:aurora-hoteis')
        owned = [p['id'] for p in data.core['technical_project'] if str(p['owner_company_id']) == str(aurora)]
        self.assertTrue(owned)
        member_of = {(m['technical_project_id'], m['user_id']) for m in data.core['project_member']}
        for username in ('dev_dem_manager', 'dev_dem_support'):
            self.assertTrue(all((pid, users[username]) in member_of for pid in owned), username)
        self.assertGreaterEqual(sum(1 for _, user in member_of if user == users['dev_tec_technician']), 1)

    def test_shortages_are_reported_when_the_real_pool_is_too_small(self):
        pool = ImagePool(ROOT.parent / 'mocks-warehouse' / 'manifest.json', PLAN['rng_seed'], 'x')
        data = build_dataset(PLAN, pool, TODAY)
        short = {row[0]: row[3] for row in data.image_report if row[3]}
        self.assertTrue(all(isinstance(value, int) and value > 0 for value in short.values()))
        for photo in data.core['local_unit_photo']:
            self.assertTrue(photo['public_id'].startswith('mocks/'))


@unittest.skipUnless(os.environ.get('SOLARIA_TEST_PG_DSN') and os.environ.get('SOLARIA_TEST_CORE_BASELINE'),
                     'Set an isolated PostgreSQL test DSN and the api-core migrations directory')
class SeedLoadTest(unittest.TestCase):
    def setUp(self):
        self.connection = psycopg2.connect(os.environ['SOLARIA_TEST_PG_DSN'])
        self.schema = 'seed_' + uuid.uuid4().hex
        with self.connection.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
            cursor.execute(sql.SQL('SET search_path TO {}, public').format(sql.Identifier(self.schema)))
        self.connection.commit()
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.connection.rollback()
        with self.connection.cursor() as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.connection.commit()
        self.connection.close()
        self.directory.cleanup()

    def count(self, table):
        with self.connection.cursor() as cursor:
            cursor.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table)))
            return cursor.fetchone()[0]

    def test_load_is_complete_idempotent_and_resettable(self):
        with self.connection.cursor() as cursor:
            migrations = [path for path in Path(os.environ['SOLARIA_TEST_CORE_BASELINE']).glob('V*.sql') if 'export' not in path.name]
            for migration in sorted(migrations, key=lambda path: int(path.name[1:].split('__')[0])):
                cursor.execute(migration.read_text(encoding='utf-8'))
        baseline = {table: self.count(table) for table in CORE_TABLES}
        dataset, _ = build(self.directory.name)
        load_dataset(dataset, core_connection=self.connection)
        for table in CORE_TABLES:
            self.assertEqual(baseline[table] + len(dataset.core[table]), self.count(table), table)
        load_dataset(dataset, core_connection=self.connection)
        for table in CORE_TABLES:
            self.assertEqual(baseline[table] + len(dataset.core[table]), self.count(table), f'{table} duplicou na segunda carga')
        load_dataset(dataset, reset=True, core_connection=self.connection)
        for table in CORE_TABLES:
            self.assertEqual(baseline[table], self.count(table), f'{table} nao voltou ao estado anterior')


if __name__ == '__main__':
    unittest.main()


def test_qa_exige_hash_proprio_e_nao_cria_a_conta_de_teste(monkeypatch):
    import pytest
    from seed.loader import apply_environment_overrides

    plan = {'allowed_environments': ['local', 'dev'], 'auth': {'password_hash': '$2a$10$publico'}, 'dev_test_account': {'username': 'teste'}}
    monkeypatch.setenv('ENVIRONMENT', 'qa')
    monkeypatch.delenv('SEED_PASSWORD_HASH', raising=False)
    with pytest.raises(SystemExit):
        apply_environment_overrides(dict(plan))
    monkeypatch.setenv('SEED_PASSWORD_HASH', '$2b$10$hashproprio')
    result = apply_environment_overrides({**plan, 'auth': dict(plan['auth'])})
    assert 'qa' in result['allowed_environments']
    assert result['auth']['password_hash'] == '$2b$10$hashproprio'
    assert 'dev_test_account' not in result


def test_local_nao_muda_o_plano(monkeypatch):
    from seed.loader import apply_environment_overrides

    monkeypatch.setenv('ENVIRONMENT', 'local')
    plan = {'allowed_environments': ['local', 'dev'], 'auth': {'password_hash': '$2a$10$publico'}, 'dev_test_account': {}}
    assert apply_environment_overrides(plan) == {'allowed_environments': ['local', 'dev'], 'auth': {'password_hash': '$2a$10$publico'}, 'dev_test_account': {}}
