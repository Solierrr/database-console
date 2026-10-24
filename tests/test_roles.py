import importlib.util
import os
from pathlib import Path
import unittest
import uuid

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('roles', ROOT / 'scripts/roles.py')
roles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roles)

EXISTING = {
    'brand': ['id', 'name'],
    'person': ['id', 'name', 'cpf', 'birth_date', 'fk_users'],
    'contact': ['id', 'email', 'phone'],
    'access_code': ['id', 'code'],
    'solaria_schema_history': ['version'],
}


class ContractTest(unittest.TestCase):
    def test_every_consumer_has_a_distinct_role_and_a_description(self):
        consumers = roles.load_contracts()

        self.assertEqual(len({item['role'] for item in consumers.values()}), len(consumers))
        for name, contract in consumers.items():
            self.assertTrue(contract['role'].startswith('solaria_ro_'), name)
            self.assertTrue(contract['description'], name)
            self.assertTrue('tables' in contract or contract.get('all_tables'), name)

    def test_explicit_tables_resolve_to_table_or_column_grants(self):
        contract = {'tables': {'brand': '*', 'person': ['id', 'fk_users']}}

        grants = roles.resolve_grants(contract, EXISTING)

        self.assertEqual(grants, {'brand': None, 'person': ['id', 'fk_users']})

    def test_a_table_or_column_that_does_not_exist_fails_loudly(self):
        with self.assertRaisesRegex(ValueError, 'does not exist'):
            roles.resolve_grants({'tables': {'nope': '*'}}, EXISTING)
        with self.assertRaisesRegex(ValueError, 'columns that do not exist'):
            roles.resolve_grants({'tables': {'person': ['id', 'nope']}}, EXISTING)

    def test_all_tables_drops_excluded_tables_and_columns(self):
        contract = {
            'all_tables': True,
            'exclude_tables': ['access_code', 'solaria_schema_history'],
            'exclude_columns': {'person': ['cpf', 'birth_date'], 'contact': ['email', 'phone']},
        }

        grants = roles.resolve_grants(contract, EXISTING)

        self.assertEqual(set(grants), {'brand', 'person', 'contact'})
        self.assertIsNone(grants['brand'])
        self.assertEqual(grants['person'], ['id', 'name', 'fk_users'])
        self.assertEqual(grants['contact'], ['id'])

    def test_excluding_something_that_is_gone_fails_instead_of_silently_widening(self):
        with self.assertRaisesRegex(ValueError, 'do not exist'):
            roles.resolve_grants({'all_tables': True, 'exclude_tables': ['gone']}, EXISTING)

    def test_the_databricks_proposal_hides_personal_data_and_secrets(self):
        contract = roles.load_contracts()['databricks-sync']

        self.assertIn('access_code', contract['exclude_tables'])
        self.assertIn('cpf', contract['exclude_columns']['person'])
        self.assertIn('email', contract['exclude_columns']['contact'])

    def test_no_consumer_gets_anything_but_select(self):
        allowed = ('REVOKE ALL ON ALL TABLES', 'REVOKE ALL ON SCHEMA', 'GRANT USAGE ON SCHEMA', 'GRANT SELECT')
        statements = []
        for contract in roles.load_contracts().values():
            statements += roles.build_statements(contract['role'], {'brand': None, 'person': ['id']})

        self.assertTrue(statements)
        for statement in statements:
            self.assertTrue(statement.seq[0].string.startswith(allowed), statement)


@unittest.skipUnless(os.environ.get('SOLARIA_TEST_PG_DSN'), 'Set an isolated PostgreSQL test DSN')
class RolesIntegrationTest(unittest.TestCase):
    """Papéis são do cluster, não do schema: o teste cria os dele com prefixo único e os apaga no fim."""

    def setUp(self):
        self.connection = psycopg2.connect(os.environ['SOLARIA_TEST_PG_DSN'])
        self.schema = 'test_' + uuid.uuid4().hex[:12]
        self.role = 'solaria_ro_t' + uuid.uuid4().hex[:8]
        with self.connection.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
            cursor.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(self.schema)))
        self.connection.commit()

    def tearDown(self):
        self.connection.rollback()
        with self.connection.cursor() as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
            cursor.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (self.role,))
            if cursor.fetchone():
                cursor.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(self.role)))
                cursor.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(self.role)))
        self.connection.commit()
        self.connection.close()

    def test_grants_are_select_only_and_check_catches_drift(self):
        # as funções do roles.py olham o schema public; aqui o teste usa uma tabela própria em public
        table = 't_' + uuid.uuid4().hex[:10]
        with self.connection.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE TABLE public.{} (id int, secret text)').format(sql.Identifier(table)))
        self.connection.commit()
        try:
            consumers = {'teste': {'role': self.role, 'tables': {table: ['id']}}}
            existing = {table: ['id', 'secret']}
            roles.apply(self.connection, consumers, existing)

            self.assertEqual(roles.check(self.connection, consumers, existing), [])

            with self.connection.cursor() as cursor:
                cursor.execute(sql.SQL('GRANT UPDATE ON public.{} TO {}').format(sql.Identifier(table), sql.Identifier(self.role)))
            self.connection.commit()
            problems = roles.check(self.connection, consumers, existing)
            self.assertTrue(any('UPDATE' in problem for problem in problems), problems)
        finally:
            with self.connection.cursor() as cursor:
                cursor.execute(sql.SQL('DROP TABLE IF EXISTS public.{}').format(sql.Identifier(table)))
            self.connection.commit()


if __name__ == '__main__':
    unittest.main()
