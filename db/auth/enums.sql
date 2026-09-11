-- =============================================================================
-- db/auth/enums.sql
--
-- Extensoes e tipos enumerados do banco do api-auth (Spring/Flyway).
-- Fonte de verdade real: api-auth/src/main/resources/db/migration/V1__create_auth_schema.sql
-- Este arquivo existe para leitura rapida e para ser aplicado isoladamente
-- (ex.: recriar o banco do zero em outro ambiente). Rode antes de schema.sql.
-- =============================================================================

-- gen_random_uuid() para chaves primarias.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- CITEXT para colunas de e-mail case-insensitive (primary_email, email).
CREATE EXTENSION IF NOT EXISTS citext;

-- Situacao da conta de um usuario (auth_user.status).
CREATE TYPE account_status AS ENUM (
    'ACTIVE',
    'LOCKED',
    'DISABLED'
);

-- Algoritmo HMAC usado para gerar codigos TOTP (totp_factor.algorithm).
CREATE TYPE otp_algorithm AS ENUM (
    'SHA1',
    'SHA256',
    'SHA512'
);

-- Finalidade de um token descartavel de uso unico (one_time_token.type).
CREATE TYPE one_time_token_type AS ENUM (
    'EMAIL_VERIFICATION',
    'PASSWORD_RESET',
    'ACCOUNT_LINK'
);

-- Catalogo de eventos de seguranca auditados (security_event.event_type).
CREATE TYPE security_event_type AS ENUM (
    'USER_REGISTERED',
    'LOGIN_SUCCEEDED',
    'LOGIN_FAILED',
    'LOGOUT',
    'PASSWORD_CHANGED',
    'PASSWORD_RESET_REQUESTED',
    'PASSWORD_RESET_COMPLETED',
    'FEDERATED_IDENTITY_LINKED',
    'FEDERATED_IDENTITY_UNLINKED',
    'MFA_ENABLED',
    'MFA_DISABLED',
    'MFA_CHALLENGE_FAILED',
    'REFRESH_TOKEN_REUSED',
    'SESSION_REVOKED'
);
