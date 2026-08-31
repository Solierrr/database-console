-- Catalogo de dados: metadados tecnicos de cada tabela/coluna do schema
-- normalizado, com regra de negocio e nivel de acesso.

CREATE TABLE data_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name TEXT NOT NULL,
    column_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    business_rule TEXT,
    access_level VARCHAR(20) NOT NULL DEFAULT 'PUBLIC'
        CHECK (access_level IN ('PUBLIC', 'INTERNAL', 'RESTRICTED', 'CONFIDENTIAL')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (table_name, column_name)
);
