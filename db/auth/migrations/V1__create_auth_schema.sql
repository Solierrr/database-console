-- =============================================================================
-- V1__create_auth_schema.sql
--
-- Espelho de leitura da migration Flyway real, mantida em
-- api-auth/src/main/resources/db/migration/V1__create_auth_schema.sql.
-- NAO e executada por este repositorio nem pelo Flyway do api-auth a partir
-- daqui -- e uma copia para consulta e historico. Qualquer nova migration
-- (V2, V3...) deve ser criada primeiro no repositorio api-auth e depois
-- copiada para esta pasta, nesta ordem.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TYPE account_status AS ENUM ('ACTIVE', 'LOCKED', 'DISABLED');
CREATE TYPE otp_algorithm AS ENUM ('SHA1', 'SHA256', 'SHA512');
CREATE TYPE one_time_token_type AS ENUM ('EMAIL_VERIFICATION', 'PASSWORD_RESET', 'ACCOUNT_LINK');
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

CREATE TABLE auth_user (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    primary_email CITEXT NOT NULL,
    email_verified_at TIMESTAMPTZ,
    status account_status NOT NULL DEFAULT 'ACTIVE',
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_auth_user PRIMARY KEY (id),
    CONSTRAINT uq_auth_user_primary_email UNIQUE (primary_email),
    CONSTRAINT ck_auth_user_failed_login_attempts CHECK (failed_login_attempts >= 0)
);

CREATE TABLE local_credential (
    user_id UUID NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    password_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    must_change BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_local_credential PRIMARY KEY (user_id),
    CONSTRAINT fk_local_credential_user FOREIGN KEY (user_id)
        REFERENCES auth_user (id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE federated_identity (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    authority VARCHAR(30) NOT NULL,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    email CITEXT,
    email_verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ,
    CONSTRAINT pk_federated_identity PRIMARY KEY (id),
    CONSTRAINT fk_federated_identity_user FOREIGN KEY (user_id)
        REFERENCES auth_user (id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_federated_identity_subject UNIQUE (issuer, subject),
    CONSTRAINT uq_federated_identity_user_issuer UNIQUE (user_id, issuer),
    CONSTRAINT ck_federated_identity_authority CHECK (authority IN ('FIREBASE'))
);

CREATE TABLE federated_provider_link (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    federated_identity_id UUID NOT NULL,
    provider VARCHAR(30) NOT NULL,
    provider_subject TEXT NOT NULL,
    email CITEXT,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_federated_provider_link PRIMARY KEY (id),
    CONSTRAINT fk_federated_provider_link_identity FOREIGN KEY (federated_identity_id)
        REFERENCES federated_identity (id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_federated_provider_link_identity_provider UNIQUE (federated_identity_id, provider),
    CONSTRAINT uq_federated_provider_link_external_identity UNIQUE (provider, provider_subject),
    CONSTRAINT ck_federated_provider_link_provider CHECK (provider IN ('GOOGLE', 'MICROSOFT'))
);

CREATE TABLE totp_factor (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    secret_ciphertext BYTEA NOT NULL,
    secret_nonce BYTEA NOT NULL,
    encryption_key_id VARCHAR(100) NOT NULL,
    algorithm otp_algorithm NOT NULL DEFAULT 'SHA1',
    digits SMALLINT NOT NULL DEFAULT 6,
    period_seconds SMALLINT NOT NULL DEFAULT 30,
    enabled_at TIMESTAMPTZ,
    last_used_counter BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_totp_factor PRIMARY KEY (id),
    CONSTRAINT uq_totp_factor_user UNIQUE (user_id),
    CONSTRAINT fk_totp_factor_user FOREIGN KEY (user_id)
        REFERENCES auth_user (id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT ck_totp_factor_digits CHECK (digits IN (6, 8)),
    CONSTRAINT ck_totp_factor_period CHECK (period_seconds BETWEEN 15 AND 60)
);

CREATE TABLE mfa_recovery_code (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    factor_id UUID NOT NULL,
    code_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    used_at TIMESTAMPTZ,
    CONSTRAINT pk_mfa_recovery_code PRIMARY KEY (id),
    CONSTRAINT fk_mfa_recovery_code_factor FOREIGN KEY (factor_id)
        REFERENCES totp_factor (id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_mfa_recovery_code_hash UNIQUE (factor_id, code_hash)
);

CREATE TABLE auth_session (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    device TEXT,
    authentication_methods TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    mfa_completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_access_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    revocation_reason VARCHAR(60),
    CONSTRAINT pk_auth_session PRIMARY KEY (id),
    CONSTRAINT fk_auth_session_user FOREIGN KEY (user_id)
        REFERENCES auth_user (id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT ck_auth_session_expiration CHECK (expires_at > created_at)
);

CREATE TABLE refresh_token (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    token_hash BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    replaced_by_id UUID,
    CONSTRAINT pk_refresh_token PRIMARY KEY (id),
    CONSTRAINT uq_refresh_token_hash UNIQUE (token_hash),
    CONSTRAINT fk_refresh_token_session FOREIGN KEY (session_id)
        REFERENCES auth_session (id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_refresh_token_replacement FOREIGN KEY (replaced_by_id)
        REFERENCES refresh_token (id) ON DELETE SET NULL,
    CONSTRAINT ck_refresh_token_expiration CHECK (expires_at > created_at),
    CONSTRAINT ck_refresh_token_consumption CHECK (consumed_at IS NULL OR consumed_at >= created_at),
    CONSTRAINT ck_refresh_token_revocation CHECK (revoked_at IS NULL OR revoked_at >= created_at)
);

CREATE TABLE one_time_token (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    type one_time_token_type NOT NULL,
    token_hash BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    CONSTRAINT pk_one_time_token PRIMARY KEY (id),
    CONSTRAINT uq_one_time_token_hash UNIQUE (token_hash),
    CONSTRAINT fk_one_time_token_user FOREIGN KEY (user_id)
        REFERENCES auth_user (id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT ck_one_time_token_expiration CHECK (expires_at > created_at)
);

CREATE TABLE security_event (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id UUID,
    session_id UUID,
    event_type security_event_type NOT NULL,
    succeeded BOOLEAN NOT NULL DEFAULT true,
    ip_address VARCHAR(45),
    user_agent TEXT,
    details JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_security_event PRIMARY KEY (id),
    CONSTRAINT fk_security_event_user FOREIGN KEY (user_id)
        REFERENCES auth_user (id) ON DELETE SET NULL,
    CONSTRAINT fk_security_event_session FOREIGN KEY (session_id)
        REFERENCES auth_session (id) ON DELETE SET NULL
);

CREATE TABLE outbox_event (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    aggregate_type VARCHAR(60) NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT pk_outbox_event PRIMARY KEY (id),
    CONSTRAINT ck_outbox_event_attempts CHECK (attempts >= 0)
);

CREATE INDEX idx_auth_session_user_active
    ON auth_session (user_id, created_at DESC) WHERE revoked_at IS NULL;
CREATE INDEX idx_refresh_token_session
    ON refresh_token (session_id, created_at DESC);
CREATE INDEX idx_one_time_token_user_type
    ON one_time_token (user_id, type, created_at DESC) WHERE consumed_at IS NULL;
CREATE INDEX idx_security_event_user_occurred
    ON security_event (user_id, occurred_at DESC);
CREATE INDEX idx_outbox_event_pending
    ON outbox_event (created_at) WHERE published_at IS NULL;
