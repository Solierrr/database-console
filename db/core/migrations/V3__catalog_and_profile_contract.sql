-- Execute in a transaction. No historical product measurements are inferred.
ALTER TABLE users ADD COLUMN IF NOT EXISTS connections UUID[] NOT NULL DEFAULT ARRAY[]::uuid[];

ALTER TABLE model ADD COLUMN IF NOT EXISTS type VARCHAR(32);
ALTER TABLE model ADD COLUMN IF NOT EXISTS width NUMERIC;
ALTER TABLE model ADD COLUMN IF NOT EXISTS length NUMERIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM model WHERE type IS NULL OR width IS NULL OR length IS NULL) THEN
        RAISE EXCEPTION 'Historical models need type, width and length before migration V3'
            USING HINT = 'Prepare these columns and fill them from verified product specifications; dimension cannot be converted safely.';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = current_schema() AND table_name = 'model' AND column_name = 'dimension') THEN
        ALTER TABLE model ALTER COLUMN dimension DROP NOT NULL;
    END IF;
END $$;

ALTER TABLE model ALTER COLUMN type SET NOT NULL;
ALTER TABLE model ALTER COLUMN width SET NOT NULL;
ALTER TABLE model ALTER COLUMN length SET NOT NULL;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_model_type' AND conrelid = 'model'::regclass) THEN
        ALTER TABLE model ADD CONSTRAINT ck_model_type CHECK (type IN ('MONOCRYSTALLINE', 'POLYCRYSTALLINE', 'THIN_FILM'));
    END IF;
END $$;

ALTER TABLE offer ADD COLUMN IF NOT EXISTS slug VARCHAR(160);
UPDATE offer SET slug = 'oferta-' || replace(id::text, '-', '') WHERE slug IS NULL;
ALTER TABLE offer ALTER COLUMN slug SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_offer_slug_unique ON offer (slug);
ALTER TABLE offer ADD COLUMN IF NOT EXISTS discount_percentage NUMERIC;
ALTER TABLE offer ADD COLUMN IF NOT EXISTS source_locale VARCHAR(10);
ALTER TABLE offer ADD COLUMN IF NOT EXISTS translation_status VARCHAR(32) NOT NULL DEFAULT 'PENDING';

CREATE TABLE IF NOT EXISTS offer_service_region (
    fk_offer UUID NOT NULL REFERENCES offer(id),
    region VARCHAR(120)
);
CREATE INDEX IF NOT EXISTS idx_offer_service_region_offer ON offer_service_region (fk_offer);

CREATE TABLE IF NOT EXISTS offer_translation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_offer UUID NOT NULL REFERENCES offer(id),
    locale VARCHAR(10) NOT NULL,
    title VARCHAR(160) NOT NULL,
    description TEXT NOT NULL,
    details TEXT,
    CONSTRAINT uq_offer_translation_locale UNIQUE (fk_offer, locale)
);

CREATE TABLE IF NOT EXISTS model_photo (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_model UUID NOT NULL REFERENCES model(id),
    url VARCHAR(255) NOT NULL,
    public_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_model_photo_model_created ON model_photo (fk_model, created_at DESC);

CREATE TABLE IF NOT EXISTS company_photo (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_company UUID NOT NULL REFERENCES company(id),
    type VARCHAR(255) NOT NULL CHECK (type IN ('PROFILE', 'BANNER')),
    url VARCHAR(255) NOT NULL,
    public_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS user_photo (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_user UUID NOT NULL REFERENCES users(id),
    type VARCHAR(255) NOT NULL CHECK (type IN ('PROFILE', 'BANNER')),
    url VARCHAR(255) NOT NULL,
    public_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS local_unit_photo (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_local_unit UUID NOT NULL REFERENCES local_unit(id),
    url VARCHAR(255) NOT NULL,
    public_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

ALTER TABLE technician ADD COLUMN IF NOT EXISTS slug VARCHAR(160);
UPDATE technician SET slug = 'profissional-' || replace(id::text, '-', '') WHERE slug IS NULL;
ALTER TABLE technician ALTER COLUMN slug SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_technician_slug_unique ON technician (slug);
ALTER TABLE energy_bill ADD COLUMN IF NOT EXISTS photo_url VARCHAR(255);
ALTER TABLE energy_bill ADD COLUMN IF NOT EXISTS photo_public_id VARCHAR(255);
