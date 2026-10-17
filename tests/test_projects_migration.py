import os
from pathlib import Path
import unittest
import uuid
import psycopg2
from psycopg2 import sql
ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.environ.get('SOLARIA_TEST_PG_DSN'), 'Set a disposable PostgreSQL test DSN')
class ProjectMigrationTest(unittest.TestCase):

    def setUp(self):
        self.db = psycopg2.connect(os.environ['SOLARIA_TEST_PG_DSN'])
        self.schema = 'projects_test_' + uuid.uuid4().hex
        with self.db.cursor() as c:
            c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
            c.execute(sql.SQL('SET search_path TO {}, public').format(sql.Identifier(self.schema)))
            c.execute((ROOT / 'db/core/enums.sql').read_text(encoding='utf-8'))
            c.execute((ROOT / 'db/core/schema.sql').read_text(encoding='utf-8').split('-- Projects support company/professional ownership;')[0])
            c.execute((ROOT / 'db/core/seed.sql').read_text(encoding='utf-8'))
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        with self.db.cursor() as c:
            c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.db.commit()
        self.db.close()

    def migrate(self, c):
        c.execute((ROOT / 'db/core/migrations/V24__project_workspace.sql').read_text(encoding='utf-8'))

    def test_preserves_legacy_owner_location_and_executor(self):
        project, service, person, technician, affiliation = [str(uuid.uuid4()) for _ in range(5)]
        user = '33333333-3333-3333-3333-333333333333'
        with self.db.cursor() as c:
            c.execute('SELECT u.id,u.fk_requester,r.fk_company,a.city FROM local_unit u JOIN requester r ON r.id=u.fk_requester JOIN address a ON a.id=u.fk_address LIMIT 1')
            unit, requester, company, city = c.fetchone()
            c.execute('INSERT INTO technical_project(id,fk_requester,fk_local_unit,start_date) VALUES(%s,%s,%s,now())', (project, requester, unit))
            c.execute("INSERT INTO person(id,fk_users,name,cpf,birth_date) VALUES(%s,%s,'Migration test','00000000001','2000-01-01')", (person, user))
            c.execute("INSERT INTO technician(id,fk_person,slug,status) VALUES(%s,%s,%s,'APPROVED')", (technician, person, 'migration_' + technician))
            c.execute("INSERT INTO technician_affiliation(id,fk_technician,fk_company,affiliation_type) VALUES(%s,%s,%s,'AFFILIATED')", (affiliation, technician, company))
            c.execute("INSERT INTO technical_service(id,fk_technical_project,purpose,created_at) VALUES(%s,%s,'Inspection',now())", (service, project))
            c.execute("INSERT INTO service_executor(fk_service,fk_technician_affiliation,function) VALUES(%s,%s,'Inspection')", (service, affiliation))
            self.migrate(c)
            c.execute('SELECT owner_company_id,location_city FROM technical_project WHERE id=%s', (project,))
            owner, location_city = c.fetchone()
            # o seed registra o adaptador de UUID do psycopg2 no processo; comparar por texto vale com ou sem ele
            self.assertEqual((str(company), city), (str(owner), location_city))
            c.execute('SELECT role,active FROM project_member WHERE project_id=%s AND user_id=%s', (project, user))
            self.assertEqual(('MEMBER', True), c.fetchone())
            c.execute('SELECT status,ends_at FROM project_activity WHERE technical_service_id=%s',(service,))
            self.assertEqual(('OPEN',None),c.fetchone())
            c.execute("INSERT INTO technician_affiliation(fk_technician,affiliation_type) VALUES(%s,'INDEPENDENT')", (technician,))
            c.execute("INSERT INTO technical_project(owner_user_id,name) VALUES(%s,'Personal project') RETURNING id", (user,))
            self.assertIsNotNone(c.fetchone()[0])

    def test_rejects_missing_owner_and_duplicate_cover(self):
        with self.db.cursor() as c:
            self.migrate(c)
            user = '33333333-3333-3333-3333-333333333333'
            c.execute("INSERT INTO technical_project(owner_user_id,name) VALUES(%s,'Personal project') RETURNING id", (user,))
            project = c.fetchone()[0]
            c.execute('SAVEPOINT invalid_owner')
            with self.assertRaises(psycopg2.IntegrityError):
                c.execute("INSERT INTO technical_project(name) VALUES('No owner')")
            c.execute('ROLLBACK TO SAVEPOINT invalid_owner')
            c.execute("INSERT INTO project_photo(id,project_id,name,mime,content,cover,uploaded_by) VALUES(gen_random_uuid(),%s,'a.png','image/png',decode('00','hex'),true,%s)", (project, user))
            c.execute('SAVEPOINT duplicate_cover')
            with self.assertRaises(psycopg2.IntegrityError):
                c.execute("INSERT INTO project_photo(id,project_id,name,mime,content,cover,uploaded_by) VALUES(gen_random_uuid(),%s,'b.png','image/png',decode('00','hex'),true,%s)", (project, user))
            c.execute('ROLLBACK TO SAVEPOINT duplicate_cover')
