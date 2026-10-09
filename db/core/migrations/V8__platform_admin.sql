-- Admin Solaria: super-admin de plataforma, desacoplado de user_company/position
-- (que são sempre escopados a uma empresa) — fase 06 do plano de telas web.
CREATE TABLE IF NOT EXISTS platform_admin (
    id         UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_user    UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_platform_admin PRIMARY KEY (id),
    CONSTRAINT uq_platform_admin_user UNIQUE (fk_user),
    CONSTRAINT fk_platform_admin_user FOREIGN KEY (fk_user)
        REFERENCES users (id)
);

-- Usuário de demonstração já provisionado como Admin Solaria, pra não deixar
-- a feature sem nenhum jeito de logar como platform-admin em ambiente novo.
INSERT INTO users (id, auth_id, username, active)
SELECT '55555555-9999-9999-9999-999999999999', '66666666-9999-9999-9999-999999999999', 'solaria_admin_demo', true
WHERE NOT EXISTS (SELECT 1 FROM users WHERE id = '55555555-9999-9999-9999-999999999999');

INSERT INTO platform_admin (fk_user)
SELECT '55555555-9999-9999-9999-999999999999'
WHERE NOT EXISTS (SELECT 1 FROM platform_admin WHERE fk_user = '55555555-9999-9999-9999-999999999999');
