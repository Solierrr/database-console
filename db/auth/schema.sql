-- =============================================================================
-- db/auth/schema.sql
--
-- Snapshot consolidado do schema do banco do api-auth (autenticacao, sessoes,
-- MFA e outbox de eventos). Fonte de verdade real: as migrations Flyway do
-- proprio repositorio api-auth (ver db/auth/migrations/). Este arquivo e
-- gerado a partir delas para dar uma visao completa do estado atual em um
-- unico lugar -- nao edite o schema aqui e espere refletir em producao;
-- qualquer alteracao real precisa nascer como uma nova migration V{n}__ no
-- api-auth e so entao ser replicada para este arquivo e para migrations/.
--
-- Pre-requisito: db/auth/enums.sql (extensoes e tipos ENUM).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- auth_user: identidade central de autenticacao. Um auth_user pode ter
-- credencial local (senha) e/ou identidades federadas (Google, Microsoft...).
-- -----------------------------------------------------------------------------
CREATE TABLE auth_user (
    id                     UUID NOT NULL DEFAULT gen_random_uuid(),
    primary_email          CITEXT NOT NULL,
    email_verified_at      TIMESTAMPTZ,
    status                 account_status NOT NULL DEFAULT 'ACTIVE',
    failed_login_attempts  INTEGER NOT NULL DEFAULT 0,
    locked_until           TIMESTAMPTZ,
    last_login_at          TIMESTAMPTZ,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_auth_user PRIMARY KEY (id),
    CONSTRAINT uq_auth_user_primary_email UNIQUE (primary_email),
    CONSTRAINT ck_auth_user_failed_login_attempts CHECK (failed_login_attempts >= 0)
);

-- -----------------------------------------------------------------------------
-- local_credential: subtipo 1:1 de auth_user para login com senha local.
-- PK = FK para auth_user (equivalente ao @MapsId no lado Java).
-- -----------------------------------------------------------------------------
CREATE TABLE local_credential (
    user_id               UUID NOT NULL,
    password_hash         VARCHAR(255) NOT NULL,
    password_changed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    must_change           BOOLEAN NOT NULL DEFAULT false,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_local_credential PRIMARY KEY (user_id),
    CONSTRAINT fk_local_credential_user FOREIGN KEY (user_id)
        REFERENCES auth_user (id) ON UPDATE CASCADE ON DELETE CASCADE
);

-- -----------------------------------------------------------------------------
-- federated_identity: vinculo de um auth_user com um provedor de identidade
-- federada (hoje: FIREBASE). federated_provider_link guarda os provedores
-- sociais (Google, Microsoft) linkados dentro dessa identidade federada.
-- -----------------------------------------------------------------------------
CREATE TABLE federated_identity (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    authority       VARCHAR(30) NOT NULL,
    issuer          TEXT NOT NULL,
    subject         TEXT NOT NULL,
    email           CITEXT,
    email_verified  BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ,

    CONSTRAINT pk_federated_identity PRIMARY KEY (id),
    CONSTRAINT fk_federated_identity_user FOREIGN KEY (user_id)
        REFERENCES auth_user (id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_federated_identity_subject UNIQUE (issuer, subject),
    CONSTRAINT uq_federated_identity_user_issuer UNIQUE (user_id, issuer),
    CONSTRAINT ck_federated_identity_authority CHECK (authority IN ('FIREBASE'))
);

CREATE TABLE federated_provider_link (
    id                     UUID NOT NULL DEFAULT gen_random_uuid(),
    federated_identity_id  UUID NOT NULL,
    provider               VARCHAR(30) NOT NULL,
    provider_subject       TEXT NOT NULL,
    email                  CITEXT,
    linked_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_federated_provider_link PRIMARY KEY (id),
    CONSTRAINT fk_federated_provider_link_identity FOREIGN KEY (federated_identity_id)
        REFERENCES federated_identity (id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_federated_provider_link_identity_provider UNIQUE (federated_identity_id, provider),
    CONSTRAINT uq_federated_provider_link_external_identity UNIQUE (provider, provider_subject),
    CONSTRAINT ck_federated_provider_link_provider CHECK (provider IN ('GOOGLE', 'MICROSOFT'))
);

-- -----------------------------------------------------------------------------
-- MFA: fator TOTP por usuario (1:1) e codigos de recuperacao (1:N por fator).
-- -----------------------------------------------------------------------------
CREATE TABLE totp_factor (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL,
    secret_ciphertext   BYTEA NOT NULL,
    secret_nonce        BYTEA NOT NULL,
    encryption_key_id   VARCHAR(100) NOT NULL,
    algorithm           otp_algorithm NOT NULL DEFAULT 'SHA1',
    digits              SMALLINT NOT NULL DEFAULT 6,
    period_seconds      SMALLINT NOT NULL DEFAULT 30,
    enabled_at          TIMESTAMPTZ,
    last_used_counter   BIGINT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_totp_factor PRIMARY KEY (id),
    CONSTRAINT uq_totp_factor_user UNIQUE (user_id),
    CONSTRAINT fk_totp_factor_user FOREIGN KEY (user_id)
        REFERENCES auth_user (id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT ck_totp_factor_digits CHECK (digits IN (6, 8)),
    CONSTRAINT ck_totp_factor_period CHECK (period_seconds BETWEEN 15 AND 60)
);

CREATE TABLE mfa_recovery_code (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    factor_id   UUID NOT NULL,
    code_hash   VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    used_at     TIMESTAMPTZ,

    CONSTRAINT pk_mfa_recovery_code PRIMARY KEY (id),
    CONSTRAINT fk_mfa_recovery_code_factor FOREIGN KEY (factor_id)
        REFERENCES totp_factor (id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_mfa_recovery_code_hash UNIQUE (factor_id, code_hash)
);

-- -----------------------------------------------------------------------------
-- Sessoes e tokens de acesso emitidos apos login.
-- -----------------------------------------------------------------------------
CREATE TABLE auth_session (
    id                       UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id                  UUID NOT NULL,
    ip_address               VARCHAR(45),
    user_agent               TEXT,
    device                   TEXT,
    authentication_methods   TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    mfa_completed_at         TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_access_at           TIMESTAMPTZ,
    expires_at               TIMESTAMPTZ NOT NULL,
    revoked_at               TIMESTAMPTZ,
    revocation_reason        VARCHAR(60),

    CONSTRAINT pk_auth_session PRIMARY KEY (id),
    CONSTRAINT fk_auth_session_user FOREIGN KEY (user_id)
        REFERENCES auth_user (id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT ck_auth_session_expiration CHECK (expires_at > created_at)
);

-- refresh_token forma uma cadeia de substituicao via replaced_by_id (rotacao
-- de token): cada uso consome o token atual e emite o proximo da linhagem.
CREATE TABLE refresh_token (
    id               UUID NOT NULL DEFAULT gen_random_uuid(),
    session_id       UUID NOT NULL,
    token_hash       BYTEA NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at       TIMESTAMPTZ NOT NULL,
    consumed_at      TIMESTAMPTZ,
    revoked_at       TIMESTAMPTZ,
    replaced_by_id   UUID,

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

-- -----------------------------------------------------------------------------
-- Tokens descartaveis (verificacao de e-mail, reset de senha, link de conta).
-- -----------------------------------------------------------------------------
CREATE TABLE one_time_token (
    id           UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL,
    type         one_time_token_type NOT NULL,
    token_hash   BYTEA NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,
    consumed_at  TIMESTAMPTZ,

    CONSTRAINT pk_one_time_token PRIMARY KEY (id),
    CONSTRAINT uq_one_time_token_hash UNIQUE (token_hash),
    CONSTRAINT fk_one_time_token_user FOREIGN KEY (user_id)
        REFERENCES auth_user (id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT ck_one_time_token_expiration CHECK (expires_at > created_at)
);

-- -----------------------------------------------------------------------------
-- Auditoria de seguranca (trilha de eventos) e outbox de integracao.
-- -----------------------------------------------------------------------------
CREATE TABLE security_event (
    id           UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id      UUID,
    session_id   UUID,
    event_type   security_event_type NOT NULL,
    succeeded    BOOLEAN NOT NULL DEFAULT true,
    ip_address   VARCHAR(45),
    user_agent   TEXT,
    details      JSONB,
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_security_event PRIMARY KEY (id),
    CONSTRAINT fk_security_event_user FOREIGN KEY (user_id)
        REFERENCES auth_user (id) ON DELETE SET NULL,
    CONSTRAINT fk_security_event_session FOREIGN KEY (session_id)
        REFERENCES auth_session (id) ON DELETE SET NULL
);

-- outbox_event implementa o padrao Transactional Outbox: eventos de dominio
-- (ex. UserRegistered) sao gravados na mesma transacao que a mudanca de
-- estado e depois publicados de forma assincrona (ver OutboxPollingScheduler
-- em api-auth) numa Redis Stream consumida pelo api-persistence.
CREATE TABLE outbox_event (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    aggregate_type  VARCHAR(60) NOT NULL,
    aggregate_id    UUID NOT NULL,
    event_type      VARCHAR(100) NOT NULL,
    payload         JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at    TIMESTAMPTZ,
    attempts        INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT pk_outbox_event PRIMARY KEY (id),
    CONSTRAINT ck_outbox_event_attempts CHECK (attempts >= 0)
);
