import importlib.util
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
        self.assertEqual(8, len({row['fk_profession'].name for row in self.data.core['professional_registration']}))
        self.assertEqual(30, counts['proposal'])
        self.assertEqual(150, counts['technical_service'])
        self.assertEqual(counts['users'], counts['auth_user'])
        units_by_requester = Counter(row['fk_requester'] for row in self.data.core['local_unit'])
        self.assertEqual(10, max(units_by_requester.values()))

    def test_single_test_account_has_all_development_contexts(self):
        auth = next(row for row in self.data.auth['auth_user'] if row['primary_email'] == 'teste@teste')
        user = next(row for row in self.data.core['users'] if row['auth_id'] == auth['id'])
        self.assertIsNone(user['managed_by_company_id'])
        memberships = [row for row in self.data.core['user_company'] if row['fk_users'] == user['id']]
        self.assertEqual(3, len(memberships))
        self.assertTrue(all(row['fk_position'].name == 'ADMIN' for row in memberships))
        self.assertTrue(any(row['fk_user'] == user['id'] for row in self.data.core['platform_admin']))
        person = next(row for row in self.data.core['person'] if row['fk_users'] == user['id'])
        self.assertTrue(any(row['fk_person'] == person['id'] for row in self.data.core['technician']))
        members = [row for row in self.data.core['project_member'] if row['user_id'] == user['id']]
        self.assertEqual(len(self.data.core['technical_project']), len(members))
        self.assertTrue(all(row['active'] and row['role'] == 'MANAGER' for row in members))
        credential = next(row for row in self.data.auth['local_credential'] if row['user_id'] == auth['id'])
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
        self.assertTrue(any(o['expiration_date'] < self.today_start() for o in offers))
        self.assertTrue(any(i['quantity'] == 0 for i in self.data.core['inventory']))
        statuses = Counter(s['status'] for s in self.data.core['subscription'])
        self.assertEqual(1, statuses['IN_DEBT'])
        self.assertEqual({'APPROVED', 'UNDER_ANALYSIS', 'REJECTED'}, {c['status'] for c in self.data.core['company']})

    def today_start(self):
        from datetime import datetime, time, timezone
        return datetime.combine(TODAY, time(12, 0), tzinfo=timezone.utc)

    def test_users_have_unique_photos_and_valid_identifiers(self):
        avatars = [u['avatar'] for u in self.data.core['users'] if u['avatar']]
        self.assertEqual(len(avatars), len(set(avatars)))
        usernames = [u['username'] for u in self.data.core['users']]
        self.assertEqual(len(usernames), len(set(usernames)))
        for username in usernames:
            self.assertRegex(username, r'^[a-z0-9_]{3,30}$')
        for company in self.data.core['company']:
            self.assertEqual(14, len(company['cnpj']))
        for person in self.data.core['person']:
            self.assertEqual(11, len(person['cpf']))
        self.assertFalse({u['auth_id'] for u in self.data.core['users']} - {a['id'] for a in self.data.auth['auth_user']})

    def test_company_logo_banner_and_unit_main_banner_are_never_repeated(self):
        company_images = [(p['type'], p['public_id']) for p in self.data.core['company_photo']]
        self.assertEqual(len(company_images), len(set(company_images)))
        logos = [p['public_id'] for p in self.data.core['company_photo'] if p['type'] == 'PROFILE']
        banners = [p['public_id'] for p in self.data.core['company_photo'] if p['type'] == 'BANNER']
        self.assertEqual(len(logos), len(set(logos)))
        self.assertEqual(len(banners), len(set(banners)))
        for kind in ('MAIN', 'BANNER'):
            used = [p['public_id'] for p in self.data.core['local_unit_photo'] if p['type'] == kind]
            self.assertEqual(len(used), len(set(used)), kind)
        per_unit = Counter((p['fk_local_unit'], p['type']) for p in self.data.core['local_unit_photo'] if p['type'] != 'GALLERY')
        self.assertTrue(all(count == 1 for count in per_unit.values()))

    def test_infrastructure_images_are_unique_and_panel_images_may_repeat(self):
        infra_ids = {m['id'] for m in self.data.core['model'] if m['product_type'] == 'INFRASTRUCTURE'}
        infra_images = [p['public_id'] for p in self.data.core['model_photo'] if p['fk_model'] in infra_ids]
        self.assertEqual(len(infra_images), len(set(infra_images)))
        primaries = Counter(p['fk_model'] for p in self.data.core['model_photo'] if p['is_primary'])
        self.assertTrue(all(count == 1 for count in primaries.values()))

    def test_unit_segment_images_come_from_the_matching_segment(self):
        segments = {}
        for entry in PLAN['demandants']:
            segments[entry['key']] = entry['segment']
        by_unit = {}
        for requester in self.data.core['requester']:
            by_unit[requester['id']] = requester['business_type']
        unit_owner = {u['id']: by_unit[u['fk_requester']] for u in self.data.core['local_unit']}
        for photo in self.data.core['local_unit_photo']:
            segment = unit_owner[photo['fk_local_unit']]
            self.assertIn(f'units-{segment}-', photo['public_id'])

    def test_references_point_to_existing_rows_or_known_catalog_entries(self):
        ids = {table: {row['id'] for row in rows if 'id' in row} for table, rows in self.data.core.items()}
        links = {
            'fk_address': 'address', 'fk_business_contact': 'business_contact', 'fk_company': 'company', 'fk_users': 'users',
            'fk_person': 'person', 'fk_user': 'users', 'fk_supplier': 'supplier', 'fk_brand': 'brand', 'fk_model': 'model',
            'fk_offer': 'offer', 'fk_requester': 'requester', 'fk_local_unit': 'local_unit', 'fk_proposal': 'proposal',
            'fk_proposal_item': 'proposal_item', 'fk_technician': 'technician', 'fk_professional': 'technician',
            'fk_technical_project': 'technical_project', 'fk_service': 'technical_service', 'fk_reviewer': 'users',
            'fk_professional_registration': 'professional_registration', 'fk_certification': 'certification',
            'fk_technician_affiliation': 'technician_affiliation', 'fk_creator_company': 'company', 'fk_owner_company': 'company',
            'fk_cart': 'cart', 'fk_order': 'purchase_order', 'fk_buyer': 'users',
        }
        for table, rows in self.data.core.items():
            for row in rows:
                for column, value in row.items():
                    if value is None or not column.startswith('fk_'):
                        continue
                    if isinstance(value, Ref):
                        self.assertIn(value.table, ('position', 'profession', 'company_plans'))
                        continue
                    self.assertIn(value, ids[links[column]], f'{table}.{column}')

    def test_orders_are_consistent_and_respect_who_can_buy(self):
        orders = self.data.core['purchase_order']
        items = self.data.core['order_item']
        payments = {row['fk_order']: row for row in self.data.core['order_payment']}
        supplier_by_company = {row['fk_company']: row['id'] for row in self.data.core['supplier']}
        own = {}
        for row in self.data.core['user_company']:
            if row['fk_company'] in supplier_by_company:
                own.setdefault(row['fk_users'], set()).add(supplier_by_company[row['fk_company']])
        professionals = {
            person['fk_users'] for person in self.data.core['person']
            if any(t['fk_person'] == person['id'] and t['status'] == 'APPROVED' for t in self.data.core['technician'])
        }
        self.assertEqual(len(PLAN['orders']['purchases']), len(orders))
        self.assertEqual({'PAID', 'CANCELED'}, {order['status'] for order in orders})
        self.assertTrue(self.data.core['cart'] and self.data.core['cart_item'])
        for order in orders:
            self.assertTrue(order['fk_buyer'] not in own or order['fk_buyer'] in professionals)
            lines = [row for row in items if row['fk_order'] == order['id']]
            self.assertTrue(lines)
            for line in lines:
                self.assertNotIn(line['fk_supplier'], own.get(order['fk_buyer'], set()))
            self.assertEqual(order['subtotal'], sum(line['line_total'] for line in lines))
            self.assertEqual(order['total'], order['subtotal'] + order['fee_amount'])
            self.assertEqual(Decimal('0.005'), order['fee_percentage'])
            self.assertEqual(order['total'], payments[order['id']]['amount'])
            self.assertEqual('REFUNDED' if order['status'] == 'CANCELED' else 'PAID', payments[order['id']]['status'])
        for line in items:
            self.assertEqual(line['line_total'], line['net_unit_price'] * line['quantity'])
        for cart in self.data.core['cart']:
            self.assertTrue(cart['fk_users'] not in own or cart['fk_users'] in professionals)
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
        usernames = {row['username']: row['id'] for row in data.core['users']}
        expected = {username: position for group in PLAN['dev_accounts'] for username, position in group['accounts']}
        self.assertEqual(10, len(expected))
        links = {row['fk_users']: row['fk_position'] for row in data.core['user_company']}
        for username, position in expected.items():
            self.assertIn(username, usernames)
            self.assertEqual(Ref('position', position), links[usernames[username]])
        self.assertEqual({'ADMIN', 'MANAGER', 'SALES', 'SUPPORT', 'TECHNICIAN'}, set(expected.values()))
        self.assertIn(usernames[PLAN['dev_platform_admin']], {row['fk_user'] for row in data.core['platform_admin']})
        emails = {row['primary_email'] for row in data.auth['auth_user']}
        self.assertTrue(all(f'{name}@seed.solaria.dev' in emails for name in expected))
        self.assertEqual(len(usernames), len(data.core['users']))

    def test_default_position_permissions_use_catalog_names_and_skip_admin(self):
        migrations = ' '.join(path.read_text(encoding='utf-8') for path in (ROOT / 'db' / 'core' / 'migrations').glob('V*.sql'))
        granted = PLAN['position_permissions']
        self.assertNotIn('ADMIN', granted)
        for position, names in granted.items():
            self.assertEqual(len(names), len(set(names)), position)
            for name in names:
                self.assertIn(f"'{name}'", migrations, f'{position}: permissao fora do catalogo: {name}')
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
        self.assertEqual(52, len(projects))
        members, photos, activities = {}, {}, {}
        for row in data.core['project_member']:
            members.setdefault(row['project_id'], []).append(row)
        for row in data.core['project_photo']:
            photos.setdefault(row['project_id'], []).append(row)
        for row in data.core['project_activity']:
            activities.setdefault(row['project_id'], []).append(row)
        services = Counter(row['fk_technical_project'] for row in data.core['technical_service'])
        self.assertGreater(len({row['name'] for row in projects}), 20)
        for project in projects:
            pid = project['id']
            self.assertNotEqual('Projeto técnico', project['name'])
            self.assertTrue(project['description'])
            self.assertEqual(2, len(project['location_state']))
            self.assertIn(project['status'], {'OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELED'})
            roles = {(m['user_id'], m['role']) for m in members[pid]}
            self.assertIn((project['created_by'], 'MANAGER'), roles)
            self.assertEqual(len(members[pid]), len({m['user_id'] for m in members[pid]}))
            self.assertEqual(services[pid] + 1, len(activities[pid]))
            for activity in activities[pid]:
                self.assertTrue(activity['ends_at'] is None or activity['ends_at'] > activity['starts_at'])
            covers = [p for p in photos[pid] if p['cover']]
            self.assertEqual(1, len(covers), 'cada projeto tem exatamente uma capa')
            for photo in photos[pid]:
                self.assertEqual('image/jpeg', photo['mime'])
                self.assertEqual(bytes([0xFF, 0xD8, 0xFF]), photo['content'][:3])
                self.assertLess(len(photo['content']), 8 * 1024 * 1024)
            if project['status'] == 'COMPLETED':
                self.assertIsNotNone(project['end_date'])
        self.assertGreaterEqual({p['status'] for p in projects}, {'IN_PROGRESS', 'COMPLETED', 'OPEN'})

    def test_dev_accounts_can_see_the_projects_of_their_company(self):
        pool = ImagePool(ROOT.parent / 'mocks-warehouse' / 'manifest.json', PLAN['rng_seed'], 'x')
        data = build_dataset(PLAN, pool, TODAY)
        users = {row['username']: row['id'] for row in data.core['users']}
        aurora = uuid.uuid5(uuid.UUID('6f1c1b2e-5d3a-4f7e-9a41-0c2d8b7e5a10'), 'company:aurora-hoteis')
        owned = [p['id'] for p in data.core['technical_project'] if str(p['owner_company_id']) == str(aurora)]
        self.assertTrue(owned)
        member_of = {(m['project_id'], m['user_id']) for m in data.core['project_member']}
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


@unittest.skipUnless(os.environ.get('SOLARIA_TEST_PG_DSN'), 'Set an isolated PostgreSQL test DSN')
class SeedLoadTest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('migrate', ROOT / 'scripts/migrate.py')
        self.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runner)
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
        self.runner.migrate(self.connection, 'core')
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
