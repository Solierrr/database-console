import argparse
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import psycopg2
from dotenv import dotenv_values


EMAIL = 'test@test.dev'
USERNAME = 'test_account'
PASSWORD_HASH = '$2b$10$Ft7ZU5.3IJQCU/MbeqIA2.kpPXyj1S5I.xU8o/Rlg4BbFDghriA7G'
AUTH_ID = str(uuid5(NAMESPACE_URL, 'solaria:test-account:auth'))
USER_ID = str(uuid5(NAMESPACE_URL, 'solaria:test-account:core'))


def connect(values, target):
    return psycopg2.connect(
        host=values['DB_POSTGRES_HOST'], port=values['DB_POSTGRES_PORT'],
        user=values['DB_POSTGRES_USER'], password=values['DB_POSTGRES_PASSWORD'],
        dbname=values[f'DB_POSTGRES_{target.upper()}'],
        sslmode=values.get('DB_POSTGRES_SSLMODE') or 'require', connect_timeout=10,
    )


def apply(auth, core):
    with auth, core:
        with auth.cursor() as cursor:
            cursor.execute(
                '''INSERT INTO auth_user (id, primary_email, email_verified_at, status)
                   VALUES (%s, %s, now(), 'ACTIVE')
                   ON CONFLICT (primary_email) DO UPDATE SET
                       status = 'ACTIVE', email_verified_at = COALESCE(auth_user.email_verified_at, now()),
                       failed_login_attempts = 0, locked_until = NULL, updated_at = now()
                   RETURNING id::text''',
                (AUTH_ID, EMAIL),
            )
            auth_id = cursor.fetchone()[0]
            cursor.execute(
                '''INSERT INTO local_credential (auth_user_id, password_hash, is_password_change_required)
                   VALUES (%s, %s, false)
                   ON CONFLICT (auth_user_id) DO UPDATE SET
                       password_hash = EXCLUDED.password_hash, is_password_change_required = false,
                       password_changed_at = now(), updated_at = now()''',
                (auth_id, PASSWORD_HASH),
            )
        with core.cursor() as cursor:
            cursor.execute(
                '''INSERT INTO user_account (id, auth_id, username, is_active)
                   VALUES (%s, %s, %s, true)
                   ON CONFLICT (auth_id) DO UPDATE SET is_active = true''',
                (USER_ID, auth_id, USERNAME),
            )


def main():
    parser = argparse.ArgumentParser(description='Cria ou atualiza somente a conta test@test.dev em auth e core.')
    parser.add_argument('--env-file', type=Path, default=Path('.env'))
    args = parser.parse_args()
    values = dotenv_values(args.env_file)
    missing = [key for key in (
        'DB_POSTGRES_HOST', 'DB_POSTGRES_PORT', 'DB_POSTGRES_USER',
        'DB_POSTGRES_PASSWORD', 'DB_POSTGRES_AUTH', 'DB_POSTGRES_CORE',
    ) if not values.get(key)]
    if missing:
        raise SystemExit(f'Configuracao ausente: {", ".join(missing)}')
    auth = connect(values, 'auth')
    try:
        core = connect(values, 'core')
        try:
            apply(auth, core)
        finally:
            core.close()
    finally:
        auth.close()
    print(f'Conta {EMAIL} aplicada em auth e core.')


if __name__ == '__main__':
    try:
        main()
    except psycopg2.Error as error:
        raise SystemExit(f'Falha ao aplicar conta (SQLSTATE {error.pgcode or "connection"}).') from None
