import csv
import os
import uuid
from pathlib import Path

import psycopg2
import psycopg2.extras
import yaml
from psycopg2.extras import execute_values

from .builder import AUTH_TABLES, CATALOG_DIR, CORE_TABLES, REFERENCE_TABLES, Ref

psycopg2.extras.register_uuid()

PRIMARY_KEYS = {'local_credential': 'auth_user_id'}


def load_plan(path):
    return apply_environment_overrides(yaml.safe_load(Path(path).read_text(encoding='utf-8')))


def apply_environment_overrides(plan):
    """No QA o seed so roda com uma senha propria (SEED_PASSWORD_HASH, bcrypt) e sem a conta de teste fixa.

    A senha de desenvolvimento do plan.yaml e publica (esta no repositorio); por isso nunca vai para o QA.
    """
    if os.environ.get('ENVIRONMENT', '').lower() != 'qa':
        return plan
    password_hash = os.environ.get('SEED_PASSWORD_HASH', '')
    if not password_hash.startswith(('$2a$', '$2b$', '$2y$')):
        raise SystemExit('No QA defina SEED_PASSWORD_HASH com o bcrypt da senha das contas de teste do QA.')
    plan['allowed_environments'] = [*plan.get('allowed_environments', []), 'qa']
    plan['auth']['password_hash'] = password_hash
    plan.pop('dev_test_account', None)
    return plan


def check_environment(plan):
    environment = os.environ.get('ENVIRONMENT', '').lower()
    allowed = plan.get('allowed_environments', ['local', 'dev'])
    if environment not in allowed:
        raise SystemExit(f'Seed planejado so roda em {allowed}; ENVIRONMENT={environment!r} nao permitido.')


def connect(target):
    names = {'core': os.environ.get('SEED_CORE_DB', 'coredb'), 'auth': os.environ.get('SEED_AUTH_DB', 'authdb')}
    return psycopg2.connect(
        host=os.environ['HOST'], port=os.environ['PORT'], dbname=names[target], user=os.environ['USER'],
        password=os.environ['PASSWORD'], sslmode=os.environ.get('SSLMODE', 'require'),
    )


def catalog_rows(name):
    with open(CATALOG_DIR / f'{name}.csv', newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def ensure_reference_rows(cursor):
    cursor.execute('SELECT name FROM job_position')
    known = {row[0] for row in cursor.fetchall()}
    for row in catalog_rows('job_position'):
        if row['name'] not in known:
            cursor.execute('INSERT INTO job_position(name, accesses) VALUES (%s, %s)', (row['name'], row['accesses']))
    cursor.execute('SELECT name FROM profession')
    known = {row[0] for row in cursor.fetchall()}
    for row in catalog_rows('profession'):
        if row['name'] not in known:
            cursor.execute('INSERT INTO profession(name) VALUES (%s)', (row['name'],))
    cursor.execute('SELECT name FROM company_plan')
    known = {row[0] for row in cursor.fetchall()}
    for row in catalog_rows('company_plan'):
        if row['name'] not in known:
            cursor.execute('INSERT INTO company_plan(name, price, cycle) VALUES (%s, %s, %s)',
                           (row['name'], row['price'], row['cycle']))


def reference_ids(cursor):
    ids = {}
    for table, column in REFERENCE_TABLES.items():
        cursor.execute(f'SELECT {column}, id FROM {table}')
        ids[table] = dict(cursor.fetchall())
    return ids


def resolve(value, references):
    if isinstance(value, Ref):
        try:
            return references[value.table][value.name]
        except KeyError:
            raise KeyError(f'Referencia ausente: {value.table}/{value.name}') from None
    return value


def insert_rows(cursor, table, rows, references):
    if not rows:
        return 0
    columns = list(rows[0].keys())
    for row in rows:
        if list(row.keys()) != columns:
            raise ValueError(f'Linhas de {table} com colunas diferentes')
    values = [tuple(resolve(row[column], references) for column in columns) for row in rows]
    sql = f'INSERT INTO {table} ({", ".join(columns)}) VALUES %s ON CONFLICT DO NOTHING'
    execute_values(cursor, sql, values, page_size=500)
    return cursor.rowcount


# Tabelas filhas de projeto: no reset saem pelo projeto (e nao so pelos IDs gerados agora), porque fotos, historico e
# convites feitos depois, ou por uma versao anterior do seed, tambem referenciam os projetos que serao apagados.
PROJECT_CHILD_TABLES = ('project_photo', 'project_history', 'project_activity', 'project_invitation', 'project_member')


def delete_project_children(cursor, project_ids):
    removed = 0
    if project_ids:
        for table in PROJECT_CHILD_TABLES:
            cursor.execute(f'DELETE FROM {table} WHERE technical_project_id = ANY(%s)', (project_ids,))
            removed += cursor.rowcount
    return removed


def delete_rows(cursor, table, rows):
    key = PRIMARY_KEYS.get(table, 'id')
    ids = [row[key] for row in rows]
    if ids:
        cursor.execute(f'DELETE FROM {table} WHERE {key} = ANY(%s)', (ids,))
    return len(ids)


def load_dataset(dataset, reset=False, core_connection=None, auth_connection=None):
    summary = {}
    if auth_connection is not None:
        with auth_connection, auth_connection.cursor() as cursor:
            tables = list(reversed(AUTH_TABLES)) if reset else AUTH_TABLES
            for table in tables:
                rows = dataset.auth[table]
                summary[table] = delete_rows(cursor, table, rows) if reset else insert_rows(cursor, table, rows, {})
    if core_connection is not None:
        with core_connection, core_connection.cursor() as cursor:
            if reset:
                delete_project_children(cursor, [row['id'] for row in dataset.core['technical_project']])
                for table in reversed(CORE_TABLES):
                    summary[table] = delete_rows(cursor, table, dataset.core[table])
            else:
                ensure_reference_rows(cursor)
                references = reference_ids(cursor)
                for table in CORE_TABLES:
                    summary[table] = insert_rows(cursor, table, dataset.core[table], references)
    return summary
