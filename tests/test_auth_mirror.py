import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('check_auth_mirror', ROOT / 'scripts/check_auth_mirror.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def write(folder, files):
    for name, content in files.items():
        (Path(folder) / name).write_text(content, encoding='utf-8', newline='')


class AuthMirrorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.source = Path(self.tmp.name) / 'source'
        self.mirror = Path(self.tmp.name) / 'mirror'
        self.source.mkdir()
        self.mirror.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_leading_comments_and_line_endings_are_ignored(self):
        write(self.source, {'V1__a.sql': 'CREATE TABLE a (id int);\n'})
        write(self.mirror, {'V1__a.sql': '-- Espelho da migration do api-auth\r\n--\r\nCREATE TABLE a (id int);\r\n'})

        self.assertEqual(checker.compare(self.source, self.mirror), [])

    def test_a_changed_statement_is_reported(self):
        write(self.source, {'V1__a.sql': 'CREATE TABLE a (id int);'})
        write(self.mirror, {'V1__a.sql': 'CREATE TABLE a (id bigint);'})

        self.assertEqual(checker.compare(self.source, self.mirror), ['Conteúdo diferente: V1__a.sql'])

    def test_missing_and_extra_files_are_reported(self):
        write(self.source, {'V1__a.sql': 'select 1;', 'V2__b.sql': 'select 2;'})
        write(self.mirror, {'V1__a.sql': 'select 1;', 'V3__c.sql': 'select 3;'})

        problems = checker.compare(self.source, self.mirror)

        self.assertIn('Falta no espelho: V2__b.sql', problems)
        self.assertIn('Sobra no espelho (não existe no api-auth): V3__c.sql', problems)

    def test_the_real_mirror_matches_the_api_auth_when_it_is_next_to_this_repository(self):
        api_auth = Path(os.environ.get('API_AUTH_DIR') or ROOT.parent / 'api-auth')
        source = api_auth / checker.SOURCE_SUBDIR
        if not source.is_dir():
            self.skipTest('api-auth not found; set API_AUTH_DIR')

        self.assertEqual(checker.compare(source), [])


if __name__ == '__main__':
    unittest.main()
