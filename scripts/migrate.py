import argparse
import hashlib
import os
from pathlib import Path
import re

import psycopg2
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]


def migrations(target):
    entries = []
    for path in (ROOT / 'db' / target / 'migrations').glob('V*__*.sql'):
        match = re.fullmatch(r'V(\d+)__(.+)\.sql', path.name)
        if match:
            entries.append((int(match[1]), path, hashlib.sha256(path.read_bytes()).hexdigest()))
    entries.sort()
    if len({item[0] for item in entries}) != len(entries):
        raise ValueError('Duplicate migration versions')
    return entries


def migrate(connection, target, baseline=None):
    entries = migrations(target)
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_lock(831204, 1)')
    connection.commit()
    try:
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE IF NOT EXISTS solaria_schema_history (version INTEGER PRIMARY KEY, script TEXT NOT NULL, checksum VARCHAR(64) NOT NULL, baselined BOOLEAN NOT NULL DEFAULT FALSE, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())')
        connection.commit()
        with connection.cursor() as cursor:
            cursor.execute('SELECT version, checksum FROM solaria_schema_history')
            applied = dict(cursor.fetchall())
            if baseline is not None:
                if applied or baseline not in {item[0] for item in entries}:
                    raise ValueError('Baseline requires empty history and an existing migration version')
                for version, path, checksum in entries:
                    if version <= baseline:
                        cursor.execute('INSERT INTO solaria_schema_history(version,script,checksum,baselined) VALUES (%s,%s,%s,TRUE)', (version, path.name, checksum))
                        applied[version] = checksum
        connection.commit()
        known = {item[0] for item in entries}
        if set(applied) - known:
            raise ValueError('Applied migrations are missing locally')
        if any(version < max(applied, default=0) and version not in applied for version, _, _ in entries):
            raise ValueError('Out-of-order migrations require explicit reconciliation')
        for version, path, checksum in entries:
            if version in applied:
                if applied[version] != checksum:
                    raise ValueError(f'Checksum mismatch: {path.name}')
                continue
            with connection.cursor() as cursor:
                cursor.execute(path.read_text(encoding='utf-8-sig'))
                cursor.execute('INSERT INTO solaria_schema_history(version,script,checksum) VALUES (%s,%s,%s)', (version, path.name, checksum))
            connection.commit()
            print(f'Applied {path.name}')
    except Exception:
        connection.rollback()
        raise
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(831204, 1)')
        connection.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=['core', 'auth'], required=True)
    parser.add_argument('--baseline', type=int)
    args = parser.parse_args()
    values = {**dotenv_values(ROOT / '.env'), **os.environ}
    options = dict(host=values['DB_POSTGRES_HOST'], port=values['DB_POSTGRES_PORT'], user=values['DB_POSTGRES_USER'], password=values['DB_POSTGRES_PASSWORD'], dbname=values[f'DB_POSTGRES_{args.target.upper()}'], connect_timeout=10)
    if values.get('DB_POSTGRES_SSLMODE'):
        options['sslmode'] = values['DB_POSTGRES_SSLMODE']
    with psycopg2.connect(**options) as connection:
        migrate(connection, args.target, args.baseline)


if __name__ == '__main__':
    try:
        main()
    except psycopg2.Error as error:
        raise SystemExit(f'Migration failed (SQLSTATE {error.pgcode or "connection"}); no credentials or row data logged') from None
