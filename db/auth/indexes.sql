-- =============================================================================
-- db/auth/indexes.sql
--
-- Indices de otimizacao do banco do api-auth, alem dos indices implicitos
-- criados pelas PKs/UNIQUEs em schema.sql. Espelha os indices declarados na
-- migration V1 do api-auth. Rode apos schema.sql.
-- =============================================================================

-- Sessoes ativas de um usuario, mais recentes primeiro (dashboard "meus
-- dispositivos", checagem de sessao concorrente).
CREATE INDEX idx_auth_session_user_active
    ON auth_session (user_id, created_at DESC)
    WHERE revoked_at IS NULL;

-- Historico de refresh tokens de uma sessao (detectar reuso/rotacao).
CREATE INDEX idx_refresh_token_session
    ON refresh_token (session_id, created_at DESC);

-- Tokens descartaveis pendentes de um usuario, por tipo (evita reenviar
-- e-mail de verificacao se ja existe um token valido).
CREATE INDEX idx_one_time_token_user_type
    ON one_time_token (user_id, type, created_at DESC)
    WHERE consumed_at IS NULL;

-- Trilha de auditoria por usuario, mais recente primeiro.
CREATE INDEX idx_security_event_user_occurred
    ON security_event (user_id, occurred_at DESC);

-- Fila de eventos de outbox ainda nao publicados (consumida pelo
-- OutboxPollingScheduler).
CREATE INDEX idx_outbox_event_pending
    ON outbox_event (created_at)
    WHERE published_at IS NULL;
