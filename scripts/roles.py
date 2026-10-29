"""Papéis de acesso direto aos bancos, um por consumidor.

O contrato de cada consumidor (banco, schema, privilégios e tabelas) fica em `db/roles/contracts.json`.
Os papéis de leitura (`ro_bootstrap`, `ro_databricks`) enxergam só o schema `export` do `coredb` e do `authdb`;
o `rpa_writer` é a exceção documentada ao dono único do `coredb` e só existe em QA.
Este script cria os papéis de grupo (sem login), concede só os privilégios do contrato, confere se o banco
bate com o contrato e cria o login de um consumidor a partir de uma senha que vem de uma variável de ambiente
(nunca de arquivo).

  python scripts/roles.py apply [--only database-bootstrap] [--database core] [--environment qa]
  python scripts/roles.py check [--only ...] [--database ...] [--environment ...]   sai com 1 se divergir
  python scripts/roles.py sql   [--only ...] [--database ...] [--environment ...]   mostra os comandos sem executar
  python scripts/roles.py login database-bootstrap svc_bootstrap SENHA_ENV [--environment qa]
                                                              cria o login `svc_bootstrap` no papel do consumidor,
                                                              com a senha lida da variável de ambiente SENHA_ENV

A conexão usa DB_POSTGRES_HOST, _PORT, _USER, _PASSWORD e o nome do banco em DB_POSTGRES_CORE ou DB_POSTGRES_AUTH;
o usuário precisa poder criar papéis. O ambiente vem de --environment ou da variável ENVIRONMENT.
Depois de mudar as views do `export`, rode `apply` de novo: os papéis não herdam objetos novos.
"""
import argparse
import json
import os
from pathlib import Path

import psycopg2
from dotenv import dotenv_values
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_PATH = ROOT / 'db' / 'roles' / 'contracts.json'
TABLE_PRIVILEGES = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
CHECKED_SCHEMAS = ('public', 'export')


def load_contracts(path=CONTRACTS_PATH):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    consumers = data['consumers']
    roles = [item['role'] for item in consumers.values()]
    if len(set(roles)) != len(roles):
        raise ValueError('Duplicate role names in the contracts')
    return consumers


def list_columns(connection, schema):
    """Tabelas e views do schema e suas colunas, na ordem da tabela."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, a.attname FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped "
            "WHERE n.nspname = %s AND c.relkind IN ('r', 'p', 'v', 'm') "
            "ORDER BY c.relname, a.attnum", (schema,))
        tables = {}
        for table, column in cursor.fetchall():
            tables.setdefault(table, []).append(column)
    return tables


def resolve_grants(grant, existing):
    """Contrato -> {tabela: None (todas as colunas) | [colunas]}. Falha se citar tabela ou coluna que não existe."""
    if grant.get('all_tables'):
        return dict.fromkeys(existing)
    grants = {}
    for table, columns in grant['tables'].items():
        if table not in existing:
            raise ValueError(f'Contract names a table that does not exist: {table}')
        if columns == '*':
            grants[table] = None
            continue
        if set(grant.get('privileges', ['SELECT'])) != {'SELECT'}:
            raise ValueError(f'Column lists only work with SELECT: {table}')
        missing = [column for column in columns if column not in existing[table]]
        if missing:
            raise ValueError(f'Contract names columns that do not exist in {table}: {missing}')
        grants[table] = list(columns)
    return grants


def build_statements(role, schemas, schema, grants, privileges=('SELECT',)):
    """`schemas` são todos os schemas conferidos: o papel perde tudo neles antes de receber o contrato."""
    ident = sql.Identifier(role)
    statements = []
    for name in schemas:
        statements.append(sql.SQL('REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {}').format(sql.Identifier(name), ident))
        statements.append(sql.SQL('REVOKE ALL ON SCHEMA {} FROM {}').format(sql.Identifier(name), ident))
    statements.append(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(schema), ident))
    for table, columns in sorted(grants.items()):
        target = sql.Identifier(schema, table)
        if columns is None:
            statements.append(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(', ').join(sql.SQL(p) for p in privileges), target, ident))
        else:
            statements.append(sql.SQL('GRANT SELECT ({}) ON {} TO {}').format(
                sql.SQL(', ').join(sql.Identifier(column) for column in columns), target, ident))
    return statements


def selected(consumers, only):
    if only is None:
        return consumers
    if only not in consumers:
        raise ValueError(f'Unknown consumer {only}; use one of {sorted(consumers)}')
    return {only: consumers[only]}


def active_in(contract, environment):
    allowed = contract.get('environments')
    return allowed is None or environment in allowed


def require_environment(name, contract, environment):
    if not active_in(contract, environment):
        raise ValueError(f'{name} only exists in {contract["environments"]}; environment is {environment!r}')


def schemas_of(connection, grant):
    wanted = tuple(dict.fromkeys((*CHECKED_SCHEMAS, grant['schema'])))
    with connection.cursor() as cursor:
        cursor.execute('SELECT nspname FROM pg_namespace WHERE nspname = ANY(%s)', (list(wanted),))
        present = {row[0] for row in cursor.fetchall()}
    if grant['schema'] not in present:
        raise ValueError(f'Schema {grant["schema"]} does not exist in the database')
    return tuple(name for name in wanted if name in present)


def role_exists(connection, role):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (role,))
        return cursor.fetchone() is not None


def apply(connection, name, contract, database, existing=None):
    grant = contract['grants'][database]
    role = contract['role']
    existing = existing if existing is not None else list_columns(connection, grant['schema'])
    grants = resolve_grants(grant, existing)
    with connection.cursor() as cursor:
        if not role_exists(connection, role):
            cursor.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
        for statement in build_statements(role, schemas_of(connection, grant), grant['schema'], grants, grant.get('privileges', ['SELECT'])):
            cursor.execute(statement)
    connection.commit()
    print(f'{name}: {role} em {database} com acesso a {len(grants)} objeto(s) de {grant["schema"]}')


def has_privilege(cursor, query, *arguments):
    cursor.execute(query, arguments)
    return cursor.fetchone()[0]


def check_write_privileges(cursor, name, role, label, allowed, expected):
    problems = []
    for privilege in TABLE_PRIVILEGES:
        if privilege == 'SELECT':
            continue
        has = has_privilege(cursor, 'SELECT has_table_privilege(%s, %s, %s)', role, label, privilege)
        wanted = privilege in allowed and expected is None
        if has and not wanted:
            problems.append(f'{name}: {role} tem {privilege} em {label}')
        if wanted and not has:
            problems.append(f'{name}: {role} não tem {privilege} em {label}')
    return problems


def check_read_privileges(cursor, name, role, label, columns, expected):
    table_wide = has_privilege(cursor, 'SELECT has_table_privilege(%s, %s, %s)', role, label, 'SELECT')
    if expected is None:
        return [] if table_wide else [f'{name}: {role} não lê {label}']
    problems = []
    if table_wide:
        problems.append(f'{name}: {role} lê {label} inteira, mas o contrato libera só {expected or "nada"}')
    for column in columns:
        readable = has_privilege(cursor, 'SELECT has_column_privilege(%s, %s, %s, %s)', role, label, column, 'SELECT') and not table_wide
        if readable and column not in expected:
            problems.append(f'{name}: {role} lê {label}.{column}, que não está no contrato')
        if not readable and column in expected:
            problems.append(f'{name}: {role} não lê {label}.{column}, que está no contrato')
    return problems


def check_schema(cursor, name, role, schema, existing, expected_grants, allowed):
    problems = []
    for table, columns in existing.items():
        label = f'{schema}.{table}'
        expected = expected_grants.get(table, [])
        problems += check_write_privileges(cursor, name, role, label, allowed, expected)
        problems += check_read_privileges(cursor, name, role, label, columns, expected)
    if has_privilege(cursor, 'SELECT has_schema_privilege(%s, %s, %s)', role, schema, 'CREATE'):
        problems.append(f'{name}: {role} pode criar objetos no schema {schema}')
    return problems


def check(connection, name, contract, database, existing_by_schema=None):
    """Compara o banco com o contrato. Devolve a lista de divergências (vazia = tudo certo)."""
    grant = contract['grants'][database]
    role = contract['role']
    allowed = tuple(grant.get('privileges', ['SELECT']))
    if not role_exists(connection, role):
        return [f'{name}: o papel {role} não existe']
    problems = []
    with connection.cursor() as cursor:
        for schema in schemas_of(connection, grant):
            existing = (existing_by_schema or {}).get(schema)
            if existing is None:
                existing = list_columns(connection, schema)
            expected_grants = resolve_grants(grant, existing) if schema == grant['schema'] else {}
            problems += check_schema(cursor, name, role, schema, existing, expected_grants, allowed)
        if has_privilege(cursor, "SELECT has_database_privilege(%s, current_database(), 'CREATE')", role):
            problems.append(f'{name}: {role} pode criar objetos no banco')
    return problems


def create_login(connection, consumer, contract, login, password):
    if not password:
        raise ValueError('The password variable is empty')
    role = contract['role']
    ident = sql.Identifier(login)
    with connection.cursor() as cursor:
        if not role_exists(connection, role):
            cursor.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
        if role_exists(connection, login):
            cursor.execute(sql.SQL('ALTER ROLE {} WITH LOGIN PASSWORD {}').format(ident, sql.Literal(password)))
        else:
            cursor.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} IN ROLE {}').format(
                ident, sql.Literal(password), sql.Identifier(role)))
    connection.commit()
    print(f'{consumer}: login {login} no papel {role}')


def connect(database):
    values = {**dotenv_values(ROOT / '.env'), **os.environ}
    options = dict(host=values['DB_POSTGRES_HOST'], port=values['DB_POSTGRES_PORT'], user=values['DB_POSTGRES_USER'],
                   password=values['DB_POSTGRES_PASSWORD'], dbname=values[f'DB_POSTGRES_{database.upper()}'], connect_timeout=10)
    if values.get('DB_POSTGRES_SSLMODE'):
        options['sslmode'] = values['DB_POSTGRES_SSLMODE']
    return psycopg2.connect(**options)


def plan(consumers, environment, database):
    """Pares (consumidor, contrato, banco) a processar neste ambiente."""
    return [(name, contract, key) for name, contract in consumers.items() if active_in(contract, environment)
            for key in contract['grants'] if database in (None, key)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['apply', 'check', 'sql', 'login'])
    parser.add_argument('args', nargs='*')
    parser.add_argument('--only')
    parser.add_argument('--database', choices=['core', 'auth'])
    parser.add_argument('--environment', default=os.environ.get('ENVIRONMENT', ''))
    args = parser.parse_args()
    environment = args.environment.lower()
    consumers = load_contracts()
    if args.command == 'login':
        if len(args.args) != 3:
            parser.error('login needs: CONSUMER LOGIN PASSWORD_ENV_VAR')
        consumer, login, variable = args.args
        contract = selected(consumers, consumer)[consumer]
        require_environment(consumer, contract, environment)
        with connect(args.database or next(iter(contract['grants']))) as connection:
            create_login(connection, consumer, contract, login, os.environ.get(variable, ''))
        return
    chosen = selected(consumers, args.only)
    if args.only:
        require_environment(args.only, chosen[args.only], environment)
    problems = []
    for name, contract, database in plan(chosen, environment, args.database):
        with connect(database) as connection:
            if args.command == 'apply':
                apply(connection, name, contract, database)
            elif args.command == 'check':
                problems += check(connection, name, contract, database)
            else:
                grant = contract['grants'][database]
                print(f'-- {name} ({database})')
                for statement in build_statements(contract['role'], schemas_of(connection, grant), grant['schema'],
                                                  resolve_grants(grant, list_columns(connection, grant['schema'])),
                                                  grant.get('privileges', ['SELECT'])):
                    print(statement.as_string(connection) + ';')
    if args.command == 'check':
        for problem in problems:
            print(problem)
        print('OK: o banco bate com o contrato.' if not problems else f'{len(problems)} divergência(s).')
        raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    try:
        main()
    except psycopg2.Error as error:
        raise SystemExit(f'Roles failed (SQLSTATE {error.pgcode or "connection"}); no credentials or row data logged') from None
