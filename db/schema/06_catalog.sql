-- Dominio de catalogo (espelha api-core.catalog).

CREATE TABLE supplier (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_company UUID NOT NULL REFERENCES company (id),
    status supplier_status NOT NULL DEFAULT 'ACTIVE'
);

ALTER TABLE subscription
    ADD CONSTRAINT fk_subscription_supplier FOREIGN KEY (fk_supplier) REFERENCES supplier (id);

CREATE TABLE model (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand VARCHAR(120) NOT NULL,
    model VARCHAR(120) NOT NULL,
    type panel_type NOT NULL,
    power_wp NUMERIC(10, 2) NOT NULL,
    efficiency NUMERIC(5, 2) NOT NULL,
    width NUMERIC(8, 2) NOT NULL,
    length NUMERIC(8, 2) NOT NULL,
    weight NUMERIC(8, 2) NOT NULL,
    status model_status NOT NULL DEFAULT 'UNDER_ANALYSIS'
);

-- Subtype 1:1 de media_asset.
CREATE TABLE model_photo (
    id UUID PRIMARY KEY REFERENCES media_asset (id) ON DELETE CASCADE,
    fk_model UUID NOT NULL REFERENCES model (id)
);

CREATE TABLE offer (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_supplier UUID NOT NULL REFERENCES supplier (id),
    fk_model UUID NOT NULL REFERENCES model (id),
    unit_price NUMERIC(12, 2) NOT NULL,
    availability INT NOT NULL,
    expiration_date TIMESTAMPTZ,
    slug VARCHAR(160) NOT NULL UNIQUE,
    discount_percentage NUMERIC(5, 2),
    source_locale VARCHAR(10),
    translation_status translation_status NOT NULL DEFAULT 'PENDING'
);

-- Multivalorado no original (@ElementCollection); ja modelado como
-- tabela associativa propria -- atomico, condizente com 1FN.
CREATE TABLE offer_service_region (
    fk_offer UUID NOT NULL REFERENCES offer (id) ON DELETE CASCADE,
    region VARCHAR(120) NOT NULL,
    PRIMARY KEY (fk_offer, region)
);

CREATE TABLE offer_translation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_offer UUID NOT NULL REFERENCES offer (id),
    locale VARCHAR(10) NOT NULL,
    title VARCHAR(160) NOT NULL,
    description TEXT NOT NULL,
    details TEXT,
    UNIQUE (fk_offer, locale)
);

CREATE TABLE inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_supplier UUID NOT NULL REFERENCES supplier (id),
    fk_model UUID NOT NULL REFERENCES model (id),
    quantity INT NOT NULL
);
