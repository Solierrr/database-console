"""Papéis somente leitura do coredb, um por consumidor (T-030).

O contrato de cada consumidor (tabelas e colunas que ele lê) fica em `db/roles/contracts.json`.
Este script cria os papéis de grupo `solaria_ro_*` (sem login), concede só SELECT nas tabelas e
colunas do contrato, confere se o banco bate com o contrato e cria o usuário de login de um
consumidor a partir de uma senha que vem de uma variável de ambiente (nunca de arquivo).

  python scripts/roles.py apply [--only api-recommendation]   cria os papéis e aplica os grants
  python scripts/roles.py check [--only ...]                  confere o banco com o contrato (sai com 1 se divergir)
  python scripts/roles.py sql   [--only ...]                  mostra os comandos sem executar
  python scripts/roles.py login api-recommendation svc_recommendation SENHA_ENV
                                                              cria o login `svc_recommendation` no papel do consumidor,
                                                              com a senha lida da variável de ambiente SENHA_ENV

A conexão usa as mesmas variáveis do `migrate.py` (DB_POSTGRES_*); o usuário precisa poder criar papéis.
Depois de uma migration que cria tabelas, rode `apply` de novo: os papéis não herdam tabelas novas.
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
WRITE_PRIVILEGES = ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')


def load_contracts(path=CONTRACTS_PATH):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    consumers = data['consumers']
    roles = [item['role'] for item in consumers.values()]
    if len(set(roles)) != len(roles):
        raise ValueError('Duplicate role names in the contracts')
    return consumers


def list_columns(connection):
    """Tabelas do schema public e suas colunas, na ordem da tabela."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT t.table_name, c.column_name FROM information_schema.tables t "
            "JOIN information_schema.columns c ON c.table_schema = t.table_schema AND c.table_name = t.table_name "
            "WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE' "
            "ORDER BY t.table_name, c.ordinal_position")
        tables = {}
        for table, column in cursor.fetchall():
            tables.setdefault(table, []).append(column)
    return tables


def resolve_grants(contract, existing):
    """Contrato -> {tabela: None (todas as colunas) | [colunas]}. Falha se citar tabela ou coluna que não existe."""
    grants = {}
    if contract.get('all_tables'):
        excluded_tables = set(contract.get('exclude_tables', []))
        excluded_columns = contract.get('exclude_columns', {})
        for table, columns in existing.items():
            if table in excluded_tables:
                continue
            hidden = set(excluded_columns.get(table, []))
            grants[table] = None if not hidden else [column for column in columns if column not in hidden]
        unknown = (excluded_tables | set(excluded_columns)) - set(existing)
        if unknown:
            raise ValueError(f'Contract names tables that do not exist: {sorted(unknown)}')
    else:
        for table, columns in contract['tables'].items():
            if table not in existing:
                raise ValueError(f'Contract names a table that does not exist: {table}')
            if columns == '*':
                grants[table] = None
                continue
            missing = [column for column in columns if column not in existing[table]]
            if missing:
                raise ValueError(f'Contract names columns that do not exist in {table}: {missing}')
            grants[table] = list(columns)
    return grants


def build_statements(role, grants):
    ident = sql.Identifier(role)
    statements = [
        sql.SQL('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}').format(ident),
        sql.SQL('REVOKE ALL ON SCHEMA public FROM {}').format(ident),
        sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(ident),
    ]
    for table, columns in sorted(grants.items()):
        if columns is None:
            statements.append(sql.SQL('GRANT SELECT ON {} TO {}').format(sql.Identifier('public', table), ident))
        else:
            statements.append(sql.SQL('GRANT SELECT ({}) ON {} TO {}').format(
                sql.SQL(', ').join(sql.Identifier(column) for column in columns), sql.Identifier('public', table), ident))
    return statements


def selected(consumers, only):
    if only is None:
        return consumers
    if only not in consumers:
        raise ValueError(f'Unknown consumer {only}; use one of {sorted(consumers)}')
    return {only: consumers[only]}


def role_exists(connection, role):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (role,))
        return cursor.fetchone() is not None


def apply(connection, consumers, existing=None):
    existing = existing or list_columns(connection)
    for name, contract in consumers.items():
        role = contract['role']
        grants = resolve_grants(contract, existing)
        with connection.cursor() as cursor:
            if not role_exists(connection, role):
                cursor.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
            for statement in build_statements(role, grants):
                cursor.execute(statement)
        connection.commit()
        print(f'{name}: {role} com acesso de leitura a {len(grants)} tabela(s)')


def check(connection, consumers, existing=None):
    """Compara o banco com o contrato. Devolve a lista de divergências (vazia = tudo certo)."""
    existing = existing or list_columns(connection)
    problems = []
    with connection.cursor() as cursor:
        for name, contract in consumers.items():
            role = contract['role']
            if not role_exists(connection, role):
                problems.append(f'{name}: o papel {role} não existe')
                continue
            grants = resolve_grants(contract, existing)
            for table, columns in existing.items():
                for privilege in WRITE_PRIVILEGES:
                    cursor.execute('SELECT has_table_privilege(%s, %s, %s)', (role, f'public.{table}', privilege))
                    if cursor.fetchone()[0]:
                        problems.append(f'{name}: {role} tem {privilege} em {table}')
                cursor.execute('SELECT has_table_privilege(%s, %s, %s)', (role, f'public.{table}', 'SELECT'))
                table_wide = cursor.fetchone()[0]
                expected = grants.get(table, [])
                if expected is None:
                    if not table_wide:
                        problems.append(f'{name}: {role} não lê a tabela {table}')
                    continue
                if table_wide:
                    problems.append(f'{name}: {role} lê a tabela {table} inteira, mas o contrato libera só {expected or "nada"}')
                for column in columns:
                    cursor.execute('SELECT has_column_privilege(%s, %s, %s, %s)', (role, f'public.{table}', column, 'SELECT'))
                    allowed = cursor.fetchone()[0] and not table_wide
                    if allowed and column not in expected:
                        problems.append(f'{name}: {role} lê {table}.{column}, que não está no contrato')
                    if not allowed and column in expected:
                        problems.append(f'{name}: {role} não lê {table}.{column}, que está no contrato')
            cursor.execute("SELECT has_database_privilege(%s, current_database(), 'CREATE')", (role,))
            if cursor.fetchone()[0]:
                problems.append(f'{name}: {role} pode criar objetos no banco')
            cursor.execute("SELECT has_schema_privilege(%s, 'public', 'CREATE')", (role,))
            if cursor.fetchone()[0]:
                problems.append(f'{name}: {role} pode criar objetos no schema public')
    return problems


def create_login(connection, consumer, contract, login, password):
    if not password:
        raise ValueError('The password variable is empty')
    role = contract['role']
    ident = sql.Identifier(login)
    with connection.cursor() as cursor:
        if role_exists(connection, login):
            cursor.execute(sql.SQL('ALTER ROLE {} WITH LOGIN PASSWORD {}').format(ident, sql.Literal(password)))
        else:
            cursor.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} IN ROLE {}').format(
                ident, sql.Literal(password), sql.Identifier(role)))
    connection.commit()
    print(f'{consumer}: login {login} no papel {role}')


def connect():
    values = {**dotenv_values(ROOT / '.env'), **os.environ}
    options = dict(host=values['DB_POSTGRES_HOST'], port=values['DB_POSTGRES_PORT'], user=values['DB_POSTGRES_USER'],
                   password=values['DB_POSTGRES_PASSWORD'], dbname=values['DB_POSTGRES_CORE'], connect_timeout=10)
    if values.get('DB_POSTGRES_SSLMODE'):
        options['sslmode'] = values['DB_POSTGRES_SSLMODE']
    return psycopg2.connect(**options)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['apply', 'check', 'sql', 'login'])
    parser.add_argument('args', nargs='*')
    parser.add_argument('--only')
    args = parser.parse_args()
    consumers = load_contracts()
    with connect() as connection:
        if args.command == 'login':
            if len(args.args) != 3:
                parser.error('login needs: CONSUMER LOGIN PASSWORD_ENV_VAR')
            consumer, login, variable = args.args
            create_login(connection, consumer, selected(consumers, consumer)[consumer], login, os.environ.get(variable, ''))
            return
        chosen = selected(consumers, args.only)
        if args.command == 'apply':
            apply(connection, chosen)
        elif args.command == 'check':
            problems = check(connection, chosen)
            for problem in problems:
                print(problem)
            print('OK: o banco bate com o contrato.' if not problems else f'{len(problems)} divergência(s).')
            raise SystemExit(1 if problems else 0)
        else:
            existing = list_columns(connection)
            for name, contract in chosen.items():
                print(f'-- {name}')
                for statement in build_statements(contract['role'], resolve_grants(contract, existing)):
                    print(statement.as_string(connection) + ';')


if __name__ == '__main__':
    try:
        main()
    except psycopg2.Error as error:
        raise SystemExit(f'Roles failed (SQLSTATE {error.pgcode or "connection"}); no credentials or row data logged') from None
