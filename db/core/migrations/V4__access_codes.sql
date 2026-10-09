-- Códigos de acesso: convite de funcionário sem envio de e-mail (fase 05 do plano de telas web).
CREATE TABLE IF NOT EXISTS access_code (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_company  UUID NOT NULL,
    fk_position UUID NOT NULL,
    code        VARCHAR(12) NOT NULL,
    status      VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_access_code PRIMARY KEY (id),
    CONSTRAINT uq_access_code_code UNIQUE (code),
    CONSTRAINT fk_access_code_company FOREIGN KEY (fk_company)
        REFERENCES company (id),
    CONSTRAINT fk_access_code_position FOREIGN KEY (fk_position)
        REFERENCES position (id),
    CONSTRAINT ck_access_code_status CHECK (status IN ('ACTIVE', 'USED', 'REVOKED'))
);

CREATE INDEX IF NOT EXISTS idx_access_code_company ON access_code (fk_company);
