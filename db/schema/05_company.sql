-- Dominio de empresa (espelha api-core.company).
--
-- Decisao de normalizacao: no modelo original, "business_type" era
-- duplicado identicamente em Supplier e Requester, ambos apontando para
-- Company -- aqui o atributo sobe para a propria Company (elimina a
-- redundancia entre os dois papeis que a empresa pode assumir).

CREATE TABLE business_contact (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_email VARCHAR(100) NOT NULL,
    phone VARCHAR(12),
    website TEXT
);

CREATE TABLE company (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status company_status NOT NULL DEFAULT 'UNDER_ANALYSIS',
    fk_address UUID REFERENCES address (id),
    fk_business_contact UUID REFERENCES business_contact (id),
    cnpj CHAR(14) NOT NULL,
    trade_name VARCHAR(120) NOT NULL,
    corporate_name VARCHAR(120) NOT NULL,
    business_type VARCHAR(40),
    slug VARCHAR(160) NOT NULL UNIQUE
);

-- Subtype 1:1 de media_asset.
CREATE TABLE company_photo (
    id UUID PRIMARY KEY REFERENCES media_asset (id) ON DELETE CASCADE,
    fk_company UUID NOT NULL REFERENCES company (id),
    type photo_type NOT NULL
);

CREATE TABLE company_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) NOT NULL,
    value NUMERIC(12, 2) NOT NULL,
    cycle plan_cycle NOT NULL
);

-- N:N entre company e position (cargos disponiveis por empresa).
CREATE TABLE company_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_company UUID NOT NULL REFERENCES company (id),
    fk_position UUID NOT NULL REFERENCES position (id),
    UNIQUE (fk_company, fk_position)
);

-- N:N entre company e users, com o cargo (position) do usuario na empresa.
CREATE TABLE user_company (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_company UUID NOT NULL REFERENCES company (id),
    fk_user UUID NOT NULL REFERENCES users (id),
    fk_position UUID NOT NULL REFERENCES position (id),
    UNIQUE (fk_company, fk_user)
);

CREATE TABLE subscription (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_supplier UUID NOT NULL, -- REFERENCES supplier(id): constraint adicionada no fim de 06_catalog.sql, apos supplier existir
    fk_plan UUID NOT NULL REFERENCES company_plans (id),
    status subscription_status NOT NULL DEFAULT 'PAID',
    auto_renewal BOOLEAN NOT NULL DEFAULT TRUE,
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ
);

CREATE TABLE charge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_subscription UUID NOT NULL REFERENCES subscription (id),
    amount NUMERIC(12, 2) NOT NULL,
    payment_method payment_method NOT NULL,
    status billing_status NOT NULL DEFAULT 'PENDING',
    due_date DATE NOT NULL,
    payment_date TIMESTAMPTZ
);
