import importlib.util
import os
from pathlib import Path
import re
import unittest

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('modelagem', ROOT / 'scripts/modelagem.py')
modelagem = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modelagem)


def sql_of(name):
    return (modelagem.MODELAGEM_DIR / name).read_text(encoding='utf-8')


class ManifestTest(unittest.TestCase):
    def test_every_script_in_the_manifest_exists_and_has_a_purpose(self):
        for item in modelagem.load_manifest():
            self.assertTrue((modelagem.MODELAGEM_DIR / item['file']).is_file(), item['file'])
            self.assertTrue(item['purpose'], item['file'])

    def test_scripts_run_in_numeric_order(self):
        files = [item['file'] for item in modelagem.load_manifest()]
        self.assertEqual(sorted(files), files)

    def test_no_sql_file_is_left_out_of_the_manifest(self):
        listed = {item['file'] for item in modelagem.load_manifest()}
        on_disk = {path.name for path in modelagem.MODELAGEM_DIR.glob('*.sql')}
        self.assertEqual(on_disk, listed)

    def test_expected_objects_only_name_scripts_of_the_manifest(self):
        listed = {item['file'] for item in modelagem.load_manifest()}
        self.assertLessEqual(set(modelagem.EXPECTED), listed)

    def test_dau_is_the_only_script_for_the_auth_database(self):
        auth = [item['file'] for item in modelagem.load_manifest() if item['database'] == 'auth']
        self.assertEqual(['60_dau.sql'], auth)


class IdempotenceTest(unittest.TestCase):
    """Os scripts rodam de novo sem erro e sem apagar dados."""

    def test_objects_are_created_in_a_repeatable_way(self):
        for item in modelagem.load_manifest():
            text = sql_of(item['file'])
            self.assertNotRegex(text, r'(?i)\bCREATE\s+(?:TABLE|SCHEMA|INDEX)\s+(?!IF NOT EXISTS)', item['file'])
            self.assertNotRegex(text, r'(?i)\bCREATE\s+(?:VIEW|FUNCTION|PROCEDURE|TRIGGER)\b', item['file'])

    def test_scripts_never_drop_or_truncate(self):
        for item in modelagem.load_manifest():
            self.assertNotRegex(sql_of(item['file']), r'(?i)\b(?:DROP\s+(?:TABLE|SCHEMA|DATABASE)|TRUNCATE)\b', item['file'])


class RequirementsTest(unittest.TestCase):
    """Cada requisito de Modelagem de Dados tem o seu construto SQL em algum script."""

    def test_star_schema_has_dimensions_and_facts_written_with_ctes(self):
        text = sql_of('10_star_schema.sql')
        for name in ('dim_tempo', 'dim_fornecedor', 'dim_demandante', 'dim_modelo',
                     'fact_proposta_item', 'fact_pedido_item', 'fact_cobranca'):
            self.assertIn(f'bi.{name}', text)
        self.assertGreaterEqual(len(re.findall(r'(?im)^WITH\b', text)), 7)

    def test_bi_views_use_window_functions(self):
        text = sql_of('20_bi_views.sql')
        self.assertIn('SUM(valor_aceito) OVER (ORDER BY ano_mes)', text)
        self.assertIn('RANK() OVER (PARTITION BY estado', text)
        self.assertIn('LAG(valor_aceito) OVER', text)

    def test_at_least_two_functions_and_two_procedures(self):
        text = sql_of('30_procedures.sql')
        self.assertGreaterEqual(len(re.findall(r'CREATE OR REPLACE FUNCTION', text)), 2)
        self.assertGreaterEqual(len(re.findall(r'CREATE OR REPLACE PROCEDURE', text)), 2)

    def test_audit_triggers_record_the_full_change_on_at_least_two_tables(self):
        text = sql_of('40_audit.sql')
        for token in ('TG_OP', 'CURRENT_USER', 'to_jsonb(OLD)', 'to_jsonb(NEW)'):
            self.assertIn(token, text)
        self.assertGreaterEqual(len(re.findall(r'CREATE OR REPLACE TRIGGER trg_audit_', text)), 2)

    def test_data_catalog_describes_columns_rules_and_access_levels(self):
        text = sql_of('50_data_catalog.sql')
        for token in ('governance.data_catalog', 'business_rule', 'access_level', 'refresh_data_catalog'):
            self.assertIn(token, text)

    def test_dau_is_registered_by_a_trigger_on_the_sessions(self):
        text = sql_of('60_dau.sql')
        self.assertIn('daily_active_user', text)
        self.assertIn('AFTER INSERT ON auth_session', text)
        self.assertIn('ON CONFLICT (day, auth_user_id)', text)

    def test_the_connection_network_uses_a_recursive_cte_without_cycles(self):
        text = sql_of('70_recursiva.sql')
        self.assertIn('WITH RECURSIVE', text)
        self.assertIn('<> ALL (c.caminho)', text)


@unittest.skipUnless(os.environ.get('SOLARIA_TEST_PG_DSN') and os.environ.get('SOLARIA_TEST_CORE_BASELINE'),
                     'needs a disposable Postgres (SOLARIA_TEST_PG_DSN) and the api-core db/migration folder')
class DatabaseTest(unittest.TestCase):
    """Aplica a baseline do api-core e depois os scripts de modelagem; confere objetos e a regra de auditoria."""

    @classmethod
    def setUpClass(cls):
        cls.connection = psycopg2.connect(os.environ['SOLARIA_TEST_PG_DSN'])
        cls.connection.autocommit = True
        with cls.connection.cursor() as cursor:
            for schema in ('bi', 'regras', 'audit', 'governance'):
                cursor.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
            for migration in sorted(Path(os.environ['SOLARIA_TEST_CORE_BASELINE']).glob('V*.sql')):
                cursor.execute(migration.read_text(encoding='utf-8'))
            for item in modelagem.load_manifest():
                if item['database'] == 'core':
                    cursor.execute(sql_of(item['file']))

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def test_all_core_objects_exist(self):
        problems = []
        for item in modelagem.load_manifest():
            if item['database'] == 'core':
                problems += modelagem.check_script(self.connection, item)
        self.assertEqual([], problems)

    def test_the_second_run_changes_nothing_and_fails_nothing(self):
        with self.connection.cursor() as cursor:
            for item in modelagem.load_manifest():
                if item['database'] == 'core':
                    cursor.execute(sql_of(item['file']))

    def test_the_acceptance_rate_of_an_unknown_supplier_is_zero(self):
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT regras.taxa_aceite('00000000-0000-0000-0000-000000000000')")
            self.assertEqual(0, cursor.fetchone()[0])

    def test_recalculating_an_unknown_proposal_fails(self):
        with self.connection.cursor() as cursor:
            with self.assertRaises(psycopg2.Error):
                cursor.execute("CALL regras.recalcular_total_proposta('00000000-0000-0000-0000-000000000000')")


if __name__ == '__main__':
    unittest.main()
