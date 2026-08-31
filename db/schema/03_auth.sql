-- Dominio de autenticacao (espelha api-auth). Criado antes de identity
-- porque "users" passa a ter uma FK real para auth_user nesse banco
-- unificado (no sistema operacional isso e uma referencia solta entre
-- microsservicos).

CREATE TABLE auth_user (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    primary_email CITEXT NOT NULL UNIQUE,
    email_verified_at TIMESTAMPTZ,
    status account_status NOT NULL DEFAULT 'ACTIVE',
    failed_login_attempts INT NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Subtype 1:1 de auth_user (mesma PK/FK, igual ao @MapsId original).
CREATE TABLE local_credential (
    user_id UUID PRIMARY KEY REFERENCES auth_user (id) ON DELETE CASCADE,
    password_hash VARCHAR(255) NOT NULL,
    password_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    must_change BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE federated_identity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_user UUID NOT NULL REFERENCES auth_user (id),
    authority VARCHAR(30) NOT NULL DEFAULT 'FIREBASE',
    issuer VARCHAR(255) NOT NULL DEFAULT '',
    subject VARCHAR(255) NOT NULL DEFAULT '',
    email CITEXT,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

CREATE TABLE one_time_token (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_user UUID NOT NULL REFERENCES auth_user (id),
    token_hash BYTEA NOT NULL UNIQUE,
    type one_time_token_type NOT NULL DEFAULT 'EMAIL_VERIFICATION',
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE auth_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_user UUID NOT NULL REFERENCES auth_user (id),
    ip_address VARCHAR(45),
    user_agent TEXT,
    device VARCHAR(255),
    mfa_completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_access_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    revocation_reason VARCHAR(60)
);

-- authentication_methods era um text[] no original; normalizado (1FN) em
-- tabela associativa para manter valores atomicos.
CREATE TABLE session_authentication_method (
    fk_session UUID NOT NULL REFERENCES auth_session (id) ON DELETE CASCADE,
    method VARCHAR(60) NOT NULL,
    PRIMARY KEY (fk_session, method)
);

CREATE TABLE refresh_token (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_session UUID NOT NULL REFERENCES auth_session (id),
    token_hash BYTEA NOT NULL UNIQUE,
    consumed_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    fk_replaced_by UUID REFERENCES refresh_token (id),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE totp_factor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_user UUID NOT NULL UNIQUE REFERENCES auth_user (id),
    secret_ciphertext BYTEA NOT NULL,
    secret_nonce BYTEA NOT NULL,
    encryption_key_id VARCHAR(100) NOT NULL DEFAULT '',
    algorithm totp_algorithm NOT NULL DEFAULT 'SHA1',
    digits SMALLINT NOT NULL DEFAULT 6,
    period_seconds SMALLINT NOT NULL DEFAULT 30,
    enabled_at TIMESTAMPTZ,
    last_used_counter BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE security_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_user UUID REFERENCES auth_user (id),
    fk_session UUID REFERENCES auth_session (id),
    event_type security_event_type NOT NULL DEFAULT 'LOGIN_SUCCEEDED',
    succeeded BOOLEAN NOT NULL DEFAULT TRUE,
    ip_address VARCHAR(45),
    user_agent TEXT,
    details JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE outbox_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type VARCHAR(60) NOT NULL DEFAULT '',
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL DEFAULT '',
    payload JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    attempts INT NOT NULL DEFAULT 0
);
