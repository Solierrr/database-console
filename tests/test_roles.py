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
    'person': ['id', 'name', 'cpf', 'birth_date', 'user_id'],
    'contact': ['id', 'email', 'phone'],
}


class ContractTest(unittest.TestCase):
    def test_every_consumer_has_a_distinct_role_a_description_and_grants(self):
        consumers = roles.load_contracts()

        self.assertEqual({'ro_bootstrap', 'ro_databricks', 'rpa_writer'}, {item['role'] for item in consumers.values()})
        for name, contract in consumers.items():
            self.assertTrue(contract['description'], name)
            for database, grant in contract['grants'].items():
                self.assertIn(database, ('core', 'auth'), name)
                self.assertTrue('tables' in grant or grant.get('all_tables'), name)

    def test_read_roles_only_see_the_export_schema_and_only_select(self):
        for name, contract in roles.load_contracts().items():
            if not contract['role'].startswith('ro_'):
                continue
            for grant in contract['grants'].values():
                self.assertEqual('export', grant['schema'], name)
                self.assertEqual(['SELECT'], grant['privileges'], name)

    def test_databricks_reads_the_export_schema_of_both_databases(self):
        grants = roles.load_contracts()['databricks-sync']['grants']

        self.assertEqual({'core', 'auth'}, set(grants))
        self.assertTrue(all(grant.get('all_tables') for grant in grants.values()))

    def test_bootstrap_reads_person_and_user_account_by_column(self):
        tables = roles.load_contracts()['database-bootstrap']['grants']['core']['tables']

        self.assertEqual(['id', 'user_id'], tables['person'])
        self.assertEqual(['id', 'is_active'], tables['user_account'])
        self.assertEqual(23, len(tables))

    def test_rpa_writer_is_qa_only_and_writes_without_delete(self):
        contract = roles.load_contracts()['database-rpa']
        grant = contract['grants']['core']

        self.assertEqual(['qa'], contract['environments'])
        self.assertEqual(['SELECT', 'INSERT', 'UPDATE'], grant['privileges'])
        self.assertEqual('public', grant['schema'])
        self.assertIn('user_account', grant['tables'])
        self.assertNotIn('rpa_id_mapping', grant['tables'])
        self.assertTrue(all(columns == '*' for columns in grant['tables'].values()))
        self.assertTrue(roles.active_in(contract, 'qa'))
        self.assertFalse(roles.active_in(contract, 'local'))
        with self.assertRaisesRegex(ValueError, 'only exists'):
            roles.require_environment('database-rpa', contract, 'prod')

    def test_plan_skips_the_writer_outside_qa(self):
        consumers = roles.load_contracts()

        self.assertNotIn('database-rpa', {name for name, _, _ in roles.plan(consumers, 'local', None)})
        self.assertIn(('database-rpa', 'core'), {(name, db) for name, _, db in roles.plan(consumers, 'qa', None)})
        self.assertEqual({('databricks-sync', 'auth')}, {(name, db) for name, _, db in roles.plan(consumers, 'qa', 'auth')})

    def test_explicit_tables_resolve_to_table_or_column_grants(self):
        grant = {'tables': {'brand': '*', 'person': ['id', 'user_id']}}

        self.assertEqual({'brand': None, 'person': ['id', 'user_id']}, roles.resolve_grants(grant, EXISTING))

    def test_all_tables_grants_every_object_of_the_schema(self):
        self.assertEqual({table: None for table in EXISTING}, roles.resolve_grants({'all_tables': True}, EXISTING))

    def test_a_table_or_column_that_does_not_exist_fails_loudly(self):
        with self.assertRaisesRegex(ValueError, 'does not exist'):
            roles.resolve_grants({'tables': {'nope': '*'}}, EXISTING)
        with self.assertRaisesRegex(ValueError, 'columns that do not exist'):
            roles.resolve_grants({'tables': {'person': ['id', 'nope']}}, EXISTING)

    def test_column_lists_are_refused_for_write_privileges(self):
        with self.assertRaisesRegex(ValueError, 'only work with SELECT'):
            roles.resolve_grants({'privileges': ['SELECT', 'INSERT'], 'tables': {'person': ['id']}}, EXISTING)

    def test_statements_revoke_everything_and_grant_only_the_contract(self):
        statements = []
        for contract in roles.load_contracts().values():
            for grant in contract['grants'].values():
                statements += roles.build_statements(contract['role'], ('public', 'export'), grant['schema'],
                                                     {'brand': None, 'person': ['id']} if grant['privileges'] == ['SELECT'] else {'brand': None},
                                                     grant['privileges'])

        self.assertTrue(statements)
        for statement in statements:
            text = repr(statement)
            self.assertTrue(text.startswith(("Composed([SQL('REVOKE ALL ON", "Composed([SQL('GRANT USAGE ON SCHEMA", "Composed([SQL('GRANT ")), text)
            for forbidden in ('DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER', 'ALL PRIVILEGES', 'WITH GRANT'):
                self.assertNotIn(forbidden, text)


@unittest.skipUnless(os.environ.get('SOLARIA_TEST_PG_DSN'), 'Set an isolated PostgreSQL test DSN')
class RolesIntegrationTest(unittest.TestCase):
    """Papéis são do cluster: o teste cria os dele com prefixo único, usa tabelas e views próprias e apaga tudo no fim."""

    def setUp(self):
        self.connection = psycopg2.connect(os.environ['SOLARIA_TEST_PG_DSN'])
        suffix = uuid.uuid4().hex[:10]
        self.table = 't_' + suffix
        self.view = 'v_' + suffix
        self.role = 'ro_t' + suffix
        with self.connection.cursor() as cursor:
            cursor.execute('CREATE SCHEMA IF NOT EXISTS export')
            cursor.execute(sql.SQL('CREATE TABLE public.{} (id int, secret text)').format(sql.Identifier(self.table)))
            cursor.execute(sql.SQL('CREATE VIEW export.{} AS SELECT id, secret FROM public.{}').format(
                sql.Identifier(self.view), sql.Identifier(self.table)))
        self.connection.commit()

    def tearDown(self):
        self.connection.rollback()
        with self.connection.cursor() as cursor:
            cursor.execute(sql.SQL('DROP VIEW IF EXISTS export.{}').format(sql.Identifier(self.view)))
            cursor.execute(sql.SQL('DROP TABLE IF EXISTS public.{}').format(sql.Identifier(self.table)))
            cursor.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (self.role,))
            if cursor.fetchone():
                cursor.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(self.role)))
                cursor.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(self.role)))
        self.connection.commit()
        self.connection.close()

    def contract(self, grant):
        return {'role': self.role, 'grants': {'core': grant}}

    def grant_extra(self, statement, *names):
        with self.connection.cursor() as cursor:
            cursor.execute(sql.SQL(statement).format(*(sql.Identifier(*name) for name in names), sql.Identifier(self.role)))
        self.connection.commit()

    def test_reader_sees_only_the_export_view_columns_and_check_catches_drift(self):
        contract = self.contract({'schema': 'export', 'privileges': ['SELECT'], 'tables': {self.view: ['id']}})
        roles.apply(self.connection, 'teste', contract, 'core')

        self.assertEqual([], roles.check(self.connection, 'teste', contract, 'core'))

        self.grant_extra('GRANT SELECT ON {} TO {}', ('public', self.table))
        problems = roles.check(self.connection, 'teste', contract, 'core')
        self.assertTrue(any(f'public.{self.table}' in problem for problem in problems), problems)

        roles.apply(self.connection, 'teste', contract, 'core')
        self.grant_extra('GRANT UPDATE ON {} TO {}', ('export', self.view))
        problems = roles.check(self.connection, 'teste', contract, 'core')
        self.assertTrue(any('UPDATE' in problem for problem in problems), problems)

    def test_writer_gets_insert_update_select_on_its_tables_and_nothing_else(self):
        contract = self.contract({'schema': 'public', 'privileges': ['SELECT', 'INSERT', 'UPDATE'], 'tables': {self.table: '*'}})
        roles.apply(self.connection, 'teste', contract, 'core')

        self.assertEqual([], roles.check(self.connection, 'teste', contract, 'core'))

        self.grant_extra('GRANT DELETE ON {} TO {}', ('public', self.table))
        problems = roles.check(self.connection, 'teste', contract, 'core')
        self.assertTrue(any('DELETE' in problem for problem in problems), problems)

        roles.apply(self.connection, 'teste', contract, 'core')
        self.grant_extra('REVOKE INSERT ON {} FROM {}', ('public', self.table))
        problems = roles.check(self.connection, 'teste', contract, 'core')
        self.assertTrue(any('não tem INSERT' in problem for problem in problems), problems)

    def test_login_joins_the_consumer_role(self):
        contract = self.contract({'schema': 'export', 'privileges': ['SELECT'], 'all_tables': True})
        login = self.role + '_login'
        try:
            roles.create_login(self.connection, 'teste', contract, login, 'x' * 12)
            with self.connection.cursor() as cursor:
                cursor.execute('SELECT pg_has_role(%s, %s, %s)', (login, self.role, 'MEMBER'))
                self.assertTrue(cursor.fetchone()[0])
        finally:
            with self.connection.cursor() as cursor:
                cursor.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(login)))
            self.connection.commit()


if __name__ == '__main__':
    unittest.main()
