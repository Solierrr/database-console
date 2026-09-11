-- =============================================================================
-- db/auth/seed.sql
--
-- Massa de dados minima para desenvolvimento local do api-auth. NAO usar em
-- staging/producao. Os hashes abaixo sao fixtures (nao correspondem a senhas
-- reais utilizaveis) -- servem apenas para popular colunas NOT NULL e
-- exercitar joins durante o desenvolvimento.
--
-- Rode apos enums.sql + schema.sql (+ indexes.sql, opcional para seed).
-- =============================================================================

-- Usuario com login local (email + senha), MFA desligado.
INSERT INTO auth_user (id, primary_email, email_verified_at, status)
VALUES ('11111111-1111-1111-1111-111111111111', 'requester.demo@solaria.dev', now(), 'ACTIVE');

INSERT INTO local_credential (user_id, password_hash, must_change)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    '$2a$10$fixtureFixtureFixtureFuHashNaoUsarEmProducao000000000',
    false
);

-- Usuario autenticado via Google (sem senha local).
INSERT INTO auth_user (id, primary_email, email_verified_at, status)
VALUES ('22222222-2222-2222-2222-222222222222', 'supplier.demo@solaria.dev', now(), 'ACTIVE');

INSERT INTO federated_identity (id, user_id, authority, issuer, subject, email, email_verified)
VALUES (
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    '22222222-2222-2222-2222-222222222222',
    'FIREBASE',
    'https://securetoken.google.com/solaria-dev',
    'firebase-uid-demo-0001',
    'supplier.demo@solaria.dev',
    true
);

INSERT INTO federated_provider_link (federated_identity_id, provider, provider_subject, email)
VALUES (
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    'GOOGLE',
    'google-subject-demo-0001',
    'supplier.demo@solaria.dev'
);

-- Sessao ativa + refresh token para o usuario de login local.
INSERT INTO auth_session (id, user_id, ip_address, user_agent, device, authentication_methods, expires_at)
VALUES (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    '11111111-1111-1111-1111-111111111111',
    '127.0.0.1',
    'Mozilla/5.0 (fixture)',
    'seed-script',
    ARRAY['PASSWORD'],
    now() + INTERVAL '7 days'
);

INSERT INTO refresh_token (id, session_id, token_hash, expires_at)
VALUES (
    'cccccccc-cccc-cccc-cccc-cccccccccccc',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    decode('deadbeef00000000000000000000000000000000000000000000000000000000', 'hex'),
    now() + INTERVAL '7 days'
);

-- Evento de auditoria para o login que abriu a sessao acima.
INSERT INTO security_event (user_id, session_id, event_type, succeeded, ip_address)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    'LOGIN_SUCCEEDED',
    true,
    '127.0.0.1'
);
