"""Scripts de modelagem de dados aplicados por cima do schema do Flyway.

A DDL do `coredb` e do `authdb` pertence ao Flyway do `api-core` e do `api-auth`. Os objetos de modelagem
(esquema estrela, views de BI, functions e procedures, auditoria, catálogo de dados, DAU e consulta recursiva)
ficam em `db/modelagem/` e são aplicados aqui, na ordem do `manifest.json`. Cada script é idempotente.

  python scripts/modelagem.py list                                  lista os scripts e o banco de cada um
  python scripts/modelagem.py apply [--database core] [--dry-run]   aplica; com --dry-run desfaz tudo no fim
  python scripts/modelagem.py check [--database core]               sai com 1 se faltar algum objeto

A conexão usa DB_POSTGRES_HOST, _PORT, _USER, _PASSWORD e o nome do banco em DB_POSTGRES_CORE ou
DB_POSTGRES_AUTH (arquivo `.env` ou variáveis de ambiente). Sem --dry-run, cada script é confirmado ao terminar:
se um falhar, os anteriores continuam aplicados e os seguintes não rodam. Com --dry-run, tudo vira uma transação só
desfeita no fim.
"""
import argparse
import json
import os
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
MODELAGEM_DIR = ROOT / 'db' / 'modelagem'
MANIFEST_PATH = MODELAGEM_DIR / 'manifest.json'

# Objetos que cada script deve deixar no banco; o `check` confere se existem.
EXPECTED = {
    '10_star_schema.sql': {
        'view': ['bi.dim_tempo', 'bi.dim_fornecedor', 'bi.dim_demandante', 'bi.dim_modelo',
                 'bi.fact_proposta_item', 'bi.fact_pedido_item', 'bi.fact_cobranca'],
    },
    '20_bi_views.sql': {
        'view': ['bi.vw_valor_aceito_mensal', 'bi.vw_ranking_fornecedores', 'bi.vw_ranking_modelos',
                 'bi.vw_receita_assinaturas_mensal'],
    },
    '30_procedures.sql': {
        'function': ['regras.valor_proposta', 'regras.taxa_aceite'],
        'procedure': ['regras.recalcular_total_proposta', 'regras.cancelar_propostas_paradas'],
    },
    '40_audit.sql': {
        'table': ['audit.log'],
        'function': ['audit.fn_audit'],
        'trigger': ['trg_audit_purchase_order', 'trg_audit_offer', 'trg_audit_proposal'],
    },
    '50_data_catalog.sql': {
        'table': ['governance.data_catalog', 'governance.table_rule'],
        'procedure': ['governance.refresh_data_catalog'],
    },
    '60_dau.sql': {
        'table': ['monitoring.daily_active_user'],
        'view': ['monitoring.vw_dau'],
        'trigger': ['trg_auth_session_dau'],
    },
    '70_recursiva.sql': {
        'view': ['bi.vw_rede_conexoes', 'bi.vw_alcance_conexoes'],
    },
}


def load_manifest(path=MANIFEST_PATH):
    scripts = json.loads(Path(path).read_text(encoding='utf-8'))['scripts']
    files = [item['file'] for item in scripts]
    if len(set(files)) != len(files):
        raise ValueError('Duplicate script names in the manifest')
    for item in scripts:
        if item['database'] not in ('core', 'auth'):
            raise ValueError(f'Unknown database in the manifest: {item["database"]}')
    return scripts


def select(scripts, database):
    return [item for item in scripts if database in (None, item['database'])]


def connect(database):
    values = {**dotenv_values(ROOT / '.env'), **os.environ}
    options = dict(host=values['DB_POSTGRES_HOST'], port=values['DB_POSTGRES_PORT'], user=values['DB_POSTGRES_USER'],
                   password=values['DB_POSTGRES_PASSWORD'], dbname=values[f'DB_POSTGRES_{database.upper()}'], connect_timeout=10)
    if values.get('DB_POSTGRES_SSLMODE'):
        options['sslmode'] = values['DB_POSTGRES_SSLMODE']
    return psycopg2.connect(**options)


def apply_script(connection, item, dry_run):
    text = (MODELAGEM_DIR / item['file']).read_text(encoding='utf-8')
    with connection.cursor() as cursor:
        cursor.execute(text)
    if dry_run:
        print(f'{item["file"]} ({item["database"]}): ok (--dry-run, será desfeito no fim)')
    else:
        connection.commit()
        print(f'{item["file"]} ({item["database"]}): aplicado')


def object_exists(cursor, kind, name):
    schema, _, short = name.rpartition('.')
    if kind in ('view', 'table'):
        cursor.execute(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relname = %s AND c.relkind = ANY(%s)",
            (schema, short, ['v', 'm'] if kind == 'view' else ['r', 'p']))
    elif kind in ('function', 'procedure'):
        cursor.execute(
            "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = %s AND p.proname = %s AND p.prokind = %s",
            (schema, short, 'f' if kind == 'function' else 'p'))
    else:
        cursor.execute("SELECT 1 FROM pg_trigger WHERE tgname = %s AND NOT tgisinternal", (name,))
    return cursor.fetchone() is not None


def check_script(connection, item):
    problems = []
    with connection.cursor() as cursor:
        for kind, names in EXPECTED.get(item['file'], {}).items():
            for name in names:
                if not object_exists(cursor, kind, name):
                    problems.append(f'{item["file"]}: falta {kind} {name}')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['list', 'apply', 'check'])
    parser.add_argument('--database', choices=['core', 'auth'])
    parser.add_argument('--dry-run', action='store_true', help='aplica e desfaz, só para validar o SQL')
    args = parser.parse_args()
    scripts = select(load_manifest(), args.database)
    if args.command == 'list':
        for item in scripts:
            print(f'{item["file"]:24} {item["database"]:5} {item["purpose"]}')
        return
    problems = []
    for database in ('core', 'auth'):
        chosen = [item for item in scripts if item['database'] == database]
        if not chosen:
            continue
        with connect(database) as connection:
            for item in chosen:
                if args.command == 'apply':
                    apply_script(connection, item, args.dry_run)
                else:
                    problems += check_script(connection, item)
            if args.command == 'apply' and args.dry_run:
                # Os scripts de um banco dependem uns dos outros: o --dry-run roda todos na mesma transação.
                connection.rollback()
                print(f'{database}: tudo desfeito (--dry-run)')
    if args.command == 'check':
        for problem in problems:
            print(problem)
        print('OK: todos os objetos de modelagem existem.' if not problems else f'{len(problems)} objeto(s) faltando.')
        raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    try:
        main()
    except psycopg2.Error as error:
        raise SystemExit(f'Modelagem failed (SQLSTATE {error.pgcode or "connection"}): {(error.diag.message_primary or "").strip()}') from None
