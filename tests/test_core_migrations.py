import importlib.util
import os
from pathlib import Path
import unittest
import uuid

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('migrate', ROOT / 'scripts/migrate.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@unittest.skipUnless(os.environ.get('SOLARIA_TEST_PG_DSN'), 'Set an isolated PostgreSQL test DSN')
class CoreMigrationsTest(unittest.TestCase):
    def setUp(self):
        self.connection = psycopg2.connect(os.environ['SOLARIA_TEST_PG_DSN'])
        self.schema = 'test_' + uuid.uuid4().hex
        with self.connection.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
            cursor.execute(sql.SQL('SET search_path TO {}, public').format(sql.Identifier(self.schema)))
        self.connection.commit()

    def tearDown(self):
        self.connection.rollback()
        with self.connection.cursor() as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.connection.commit()
        self.connection.close()

    def execute(self, statement, parameters=None):
        with self.connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            return cursor.fetchall() if cursor.description else None

    def seed(self):
        seed = (ROOT / 'db/core/seed.sql').read_text(encoding='utf-8-sig')
        legacy = self.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='model' AND column_name='brand'")[0][0]
        if legacy:
            seed = seed.replace("INSERT INTO brand(id,name,normalized_name,visibility) VALUES ('bbbbbbbb-0000-0000-0000-000000000001','SolarTech','solartech','PUBLIC');", "")
            seed = seed.replace('INSERT INTO model (id, fk_brand,', 'INSERT INTO model (id, brand,').replace("    'bbbbbbbb-0000-0000-0000-000000000001',", "    'SolarTech',")
        self.execute(seed)
        self.connection.commit()

    def test_clean_upgrade_and_repeat_preserve_data(self):
        for version, path, _ in runner.migrations('core'):
            if version <= 11:
                self.execute(path.read_text(encoding='utf-8-sig'))
        self.connection.commit()
        self.seed()
        before = self.execute('SELECT id, username FROM users ORDER BY id')
        runner.migrate(self.connection, 'core', baseline=11)
        self.assertEqual(before, self.execute('SELECT id, username FROM users ORDER BY id'))
        runner.migrate(self.connection, 'core')
        self.assertEqual(len(runner.migrations('core')), self.execute('SELECT count(*) FROM solaria_schema_history')[0][0])

    def test_brand_migration_preserves_models_offers_and_consolidates_names(self):
        for version, path, _ in runner.migrations('core'):
            if version <= 19: self.execute(path.read_text(encoding='utf-8-sig'))
        self.seed()
        self.execute("INSERT INTO model(id,brand,model,power_wp,efficiency,type,width,length,weight,status) SELECT gen_random_uuid(),' solartech ','Extra',power_wp,efficiency,type,width,length,weight,status FROM model LIMIT 1")
        before = self.execute('SELECT id, slug FROM offer ORDER BY id')
        self.execute((ROOT / 'db/core/migrations/V20__brand_catalog.sql').read_text(encoding='utf-8'))
        self.assertEqual(before, self.execute('SELECT id, slug FROM offer ORDER BY id'))
        self.assertEqual([(1,)], self.execute('SELECT count(DISTINCT fk_brand) FROM model'))
        self.assertEqual([('PRIVATE', True, None)], self.execute('SELECT visibility,legacy,fk_owner_company FROM brand'))
        self.assertEqual([('PENDING',)], self.execute('SELECT status FROM brand_request'))

    def test_brand_constraints_enforce_public_uniqueness_and_pending_snapshot(self):
        runner.migrate(self.connection, 'core')
        self.seed()
        for statement in [
            "INSERT INTO brand(name,normalized_name,visibility) VALUES ('Solartech','solartech','PUBLIC')",
            "UPDATE brand SET archived=true WHERE visibility='PUBLIC'",
            "INSERT INTO brand_request(fk_brand,kind,status,proposed_name) SELECT id,'PUBLICATION','REJECTED',name FROM brand LIMIT 1",
        ]:
            self.execute('SAVEPOINT invalid_brand')
            with self.assertRaises(psycopg2.IntegrityError): self.execute(statement)
            self.execute('ROLLBACK TO SAVEPOINT invalid_brand')
        self.execute("INSERT INTO brand_request(fk_brand,kind,proposed_name) SELECT id,'CORRECTION',name FROM brand LIMIT 1")
        self.execute('SAVEPOINT duplicate_request')
        with self.assertRaises(psycopg2.IntegrityError):
            self.execute("INSERT INTO brand_request(fk_brand,kind,proposed_name) SELECT id,'CORRECTION',name FROM brand LIMIT 1")
        self.execute('ROLLBACK TO SAVEPOINT duplicate_request')

    def test_primary_photo_backfill_and_unique_constraint(self):
        for version, path, _ in runner.migrations('core'):
            if version <= 18:
                self.execute(path.read_text(encoding='utf-8-sig'))
        self.seed()
        model_id = self.execute('SELECT id FROM model LIMIT 1')[0][0]
        self.execute("INSERT INTO model_photo(fk_model,url,public_id,created_at) VALUES (%s,'older','older',now()-interval '1 day'),(%s,'latest','latest',now())", (model_id, model_id))
        migration = ROOT / 'db/core/migrations/V19__model_primary_photo.sql'
        self.execute(migration.read_text(encoding='utf-8-sig'))
        self.assertEqual([('latest',)], self.execute('SELECT url FROM model_photo WHERE fk_model=%s AND is_primary', (model_id,)))
        self.execute(migration.read_text(encoding='utf-8-sig'))
        self.execute('SAVEPOINT duplicate_primary')
        with self.assertRaises(psycopg2.IntegrityError):
            self.execute("INSERT INTO model_photo(fk_model,url,public_id,created_at,is_primary) VALUES (%s,'duplicate','duplicate',now(),true)", (model_id,))
        self.execute('ROLLBACK TO SAVEPOINT duplicate_primary')

    def test_product_type_and_unit_photo_roles(self):
        runner.migrate(self.connection, 'core')
        self.seed()
        self.assertEqual([('PANEL',)], self.execute('SELECT DISTINCT product_type FROM model'))
        brand_id = self.execute('SELECT id FROM brand LIMIT 1')[0][0]
        self.execute("INSERT INTO model(fk_brand,model,product_type,infrastructure_type,material) VALUES (%s,'Trilho 4200','INFRASTRUCTURE','RAIL','ALUMINIUM')", (brand_id,))
        for statement in [
            "INSERT INTO model(fk_brand,model,product_type) VALUES (%s,'Painel sem potencia','PANEL')",
            "INSERT INTO model(fk_brand,model,product_type) VALUES (%s,'Infra sem tipo','INFRASTRUCTURE')",
            "INSERT INTO model(fk_brand,model,product_type,infrastructure_type,power_wp) VALUES (%s,'Infra com potencia','INFRASTRUCTURE','CLAMP',400)",
            "INSERT INTO model(fk_brand,model,product_type,infrastructure_type) VALUES (%s,'Tipo invalido','INFRASTRUCTURE','WHEEL')",
        ]:
            self.execute('SAVEPOINT invalid_product')
            with self.subTest(statement=statement):
                with self.assertRaises(psycopg2.IntegrityError): self.execute(statement, (brand_id,))
            self.execute('ROLLBACK TO SAVEPOINT invalid_product')
        unit_id = self.execute('SELECT id FROM local_unit LIMIT 1')[0][0]
        self.execute("INSERT INTO local_unit_photo(fk_local_unit,type,url,public_id,created_at) VALUES (%s,'MAIN','u1','p1',now()),(%s,'BANNER','u2','p2',now()),(%s,'GALLERY','u3','p3',now()),(%s,'GALLERY','u4','p4',now())", (unit_id,) * 4)
        for kind in ('MAIN', 'BANNER'):
            self.execute('SAVEPOINT duplicate_role')
            with self.subTest(kind=kind):
                with self.assertRaises(psycopg2.IntegrityError):
                    self.execute("INSERT INTO local_unit_photo(fk_local_unit,type,url,public_id,created_at) VALUES (%s,%s,'dup','dup',now())", (unit_id, kind))
            self.execute('ROLLBACK TO SAVEPOINT duplicate_role')

    def test_photo_crop_columns_are_all_or_nothing(self):
        runner.migrate(self.connection, 'core')
        self.seed()
        user_id = self.execute('SELECT id FROM users LIMIT 1')[0][0]
        self.execute("INSERT INTO user_photo(fk_user,type,url,public_id,created_at) VALUES (%s,'PROFILE','u','p',now())", (user_id,))
        self.execute('UPDATE user_photo SET crop_x=10,crop_y=20,crop_width=300,crop_height=300')
        self.assertEqual([(10, 20, 300, 300)], self.execute('SELECT crop_x,crop_y,crop_width,crop_height FROM user_photo'))
        for statement in [
            'UPDATE user_photo SET crop_x=NULL',
            'UPDATE user_photo SET crop_width=0',
            'UPDATE user_photo SET crop_x=-1',
        ]:
            self.execute('SAVEPOINT invalid_crop')
            with self.subTest(statement=statement):
                with self.assertRaises(psycopg2.IntegrityError): self.execute(statement)
            self.execute('ROLLBACK TO SAVEPOINT invalid_crop')
        self.execute('UPDATE user_photo SET crop_x=NULL,crop_y=NULL,crop_width=NULL,crop_height=NULL')
        company_id = self.execute('SELECT id FROM company LIMIT 1')[0][0]
        self.execute("INSERT INTO company_photo(fk_company,type,url,public_id,created_at) VALUES (%s,'BANNER','u','p',now())", (company_id,))
        self.execute('SAVEPOINT invalid_company_crop')
        with self.assertRaises(psycopg2.IntegrityError): self.execute('UPDATE company_photo SET crop_x=1')
        self.execute('ROLLBACK TO SAVEPOINT invalid_company_crop')

    def test_integrity_rejects_duplicate_stock_invalid_price_and_missing_storage(self):
        runner.migrate(self.connection, 'core')
        self.seed()
        self.execute('INSERT INTO inventory(id,fk_supplier,fk_model,quantity) SELECT gen_random_uuid(),fk_supplier,fk_model,5 FROM offer LIMIT 1')
        for statement in [
            'INSERT INTO inventory(id,fk_supplier,fk_model,quantity) SELECT gen_random_uuid(),fk_supplier,fk_model,quantity FROM inventory LIMIT 1',
            'UPDATE offer SET unit_price=-1',
            'UPDATE offer SET discount_percentage=101',
            "INSERT INTO professional_document(id,user_id,kind,content_type,sha256,created_at) SELECT gen_random_uuid(),id,'IDENTITY','image/png',repeat('a',64),now() FROM users LIMIT 1",
            "UPDATE offer SET commercial_status='INVALID'",
        ]:
            self.execute('SAVEPOINT invalid_value')
            with self.subTest(statement=statement):
                with self.assertRaises(psycopg2.IntegrityError): self.execute(statement)
            self.execute('ROLLBACK TO SAVEPOINT invalid_value')

    def test_checksum_changes_and_unknown_history_are_rejected(self):
        runner.migrate(self.connection,'core')
        self.execute("UPDATE solaria_schema_history SET checksum=repeat('0',64) WHERE version=13")
        self.connection.commit()
        with self.assertRaisesRegex(ValueError,'Checksum mismatch'): runner.migrate(self.connection,'core')

    def test_workers_skip_claimed_jobs(self):
        runner.migrate(self.connection,'core')
        self.seed()
        self.execute("INSERT INTO offer_translation_job(id,offer_id,source_translation_id) SELECT gen_random_uuid(),id,gen_random_uuid() FROM offer")
        self.connection.commit()
        query = "SELECT id FROM offer_translation_job WHERE status IN ('QUEUED','RETRY_PENDING','PROCESSING') AND available_at<=now() ORDER BY available_at,id LIMIT 1 FOR UPDATE SKIP LOCKED"
        self.assertTrue(self.execute(query))
        with psycopg2.connect(os.environ['SOLARIA_TEST_PG_DSN']) as other:
            with other.cursor() as cursor:
                cursor.execute(sql.SQL('SET search_path TO {}, public').format(sql.Identifier(self.schema)))
                cursor.execute(query)
                self.assertEqual([],cursor.fetchall())

    def test_failed_migration_does_not_record_version_or_partial_ddl(self):
        runner.migrate(self.connection,'core')
        from unittest.mock import patch
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            version = max(v for v, _, _ in runner.migrations('core')) + 1
            path = Path(directory) / f'V{version}__failure.sql'
            path.write_text('CREATE TABLE must_rollback(id integer); SELECT 1/0;',encoding='utf-8')
            with patch.object(runner,'migrations',return_value=runner.migrations('core')+[(version,path,'a'*64)]):
                with self.assertRaises(psycopg2.Error): runner.migrate(self.connection,'core')
        self.assertEqual([(None,)],self.execute("SELECT to_regclass('must_rollback')"))
        self.assertEqual([(0,)],self.execute('SELECT count(*) FROM solaria_schema_history WHERE version=%s',(version,)))

    def test_snapshot_columns_match_incremental_migrations(self):
        runner.migrate(self.connection,'core')
        query = "SELECT table_name,column_name,udt_name,is_nullable FROM information_schema.columns WHERE table_schema=%s AND table_name<>'solaria_schema_history' ORDER BY 1,2"
        expected = self.execute(query,(self.schema,))
        other_schema='snapshot_'+uuid.uuid4().hex
        self.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(other_schema)))
        self.execute(sql.SQL('SET search_path TO {}, public').format(sql.Identifier(other_schema)))
        try:
            self.execute((ROOT/'db/core/enums.sql').read_text(encoding='utf-8-sig'))
            self.execute((ROOT/'db/core/schema.sql').read_text(encoding='utf-8-sig'))
            self.assertEqual(expected,self.execute(query,(other_schema,)))
        finally:
            self.connection.rollback()

    def test_concurrent_stock_creations_have_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        runner.migrate(self.connection,'core')
        self.seed()
        pair=self.execute('SELECT fk_supplier,fk_model FROM offer LIMIT 1')[0]
        statement='INSERT INTO inventory(id,fk_supplier,fk_model,quantity) VALUES (gen_random_uuid(),%s,%s,1)'
        self.execute(statement,pair)
        ready=Event()
        def contender():
            try:
                with psycopg2.connect(os.environ['SOLARIA_TEST_PG_DSN']) as other:
                    with other.cursor() as cursor:
                        cursor.execute(sql.SQL('SET search_path TO {}, public').format(sql.Identifier(self.schema)))
                        ready.set()
                        cursor.execute(statement,pair)
                return 'committed'
            except psycopg2.IntegrityError as error: return error.pgcode
        with ThreadPoolExecutor(max_workers=1) as executor:
            work=executor.submit(contender)
            self.assertTrue(ready.wait(5))
            self.connection.commit()
            self.assertEqual('23505',work.result(timeout=10))
        self.assertEqual([(1,)],self.execute('SELECT count(*) FROM inventory'))

    def test_concurrent_brand_publication_has_one_canonical_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        runner.migrate(self.connection,'core')
        self.seed()
        pair=('Concurrent Solar','concurrent solar')
        statement="INSERT INTO brand(name,normalized_name,visibility) VALUES (%s,%s,'PUBLIC')"
        self.execute(statement,pair)
        ready=Event()
        def contender():
            try:
                with psycopg2.connect(os.environ['SOLARIA_TEST_PG_DSN']) as other:
                    with other.cursor() as cursor:
                        cursor.execute(sql.SQL('SET search_path TO {}, public').format(sql.Identifier(self.schema)))
                        ready.set()
                        cursor.execute(statement,pair)
                return 'committed'
            except psycopg2.IntegrityError as error: return error.pgcode
        with ThreadPoolExecutor(max_workers=1) as executor:
            work=executor.submit(contender)
            self.assertTrue(ready.wait(5))
            self.connection.commit()
            self.assertEqual('23505',work.result(timeout=10))
        self.assertEqual([(1,)],self.execute("SELECT count(*) FROM brand WHERE normalized_name='concurrent solar'"))


if __name__ == '__main__': unittest.main()
