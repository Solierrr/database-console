ALTER TABLE model ADD COLUMN IF NOT EXISTS product_type VARCHAR(16) NOT NULL DEFAULT 'PANEL';
ALTER TABLE model ADD COLUMN IF NOT EXISTS infrastructure_type VARCHAR(16);
ALTER TABLE model ADD COLUMN IF NOT EXISTS material VARCHAR(64);

ALTER TABLE model ALTER COLUMN power_wp DROP NOT NULL;
ALTER TABLE model ALTER COLUMN efficiency DROP NOT NULL;
ALTER TABLE model ALTER COLUMN type DROP NOT NULL;
ALTER TABLE model ALTER COLUMN width DROP NOT NULL;
ALTER TABLE model ALTER COLUMN length DROP NOT NULL;
ALTER TABLE model ALTER COLUMN weight DROP NOT NULL;

ALTER TABLE model DROP CONSTRAINT IF EXISTS ck_model_type;
ALTER TABLE model ADD CONSTRAINT ck_model_type CHECK (type IS NULL OR type IN ('MONOCRYSTALLINE', 'POLYCRYSTALLINE', 'THIN_FILM'));
ALTER TABLE model ADD CONSTRAINT ck_model_product_type CHECK (product_type IN ('PANEL', 'INFRASTRUCTURE'));
ALTER TABLE model ADD CONSTRAINT ck_model_infrastructure_type CHECK (infrastructure_type IS NULL OR infrastructure_type IN ('RAIL', 'CLAMP', 'BRACKET', 'HOOK', 'KIT', 'OTHER'));
ALTER TABLE model ADD CONSTRAINT ck_model_panel_fields CHECK (
    product_type <> 'PANEL'
    OR (power_wp IS NOT NULL AND efficiency IS NOT NULL AND type IS NOT NULL AND width IS NOT NULL AND length IS NOT NULL AND weight IS NOT NULL AND infrastructure_type IS NULL)
);
ALTER TABLE model ADD CONSTRAINT ck_model_infrastructure_fields CHECK (
    product_type <> 'INFRASTRUCTURE'
    OR (infrastructure_type IS NOT NULL AND power_wp IS NULL AND efficiency IS NULL AND type IS NULL)
);
CREATE INDEX IF NOT EXISTS idx_model_product_type ON model (product_type);

ALTER TABLE local_unit_photo ADD COLUMN IF NOT EXISTS type VARCHAR(16) NOT NULL DEFAULT 'GALLERY';
ALTER TABLE local_unit_photo ADD CONSTRAINT ck_local_unit_photo_type CHECK (type IN ('MAIN', 'BANNER', 'GALLERY'));
CREATE UNIQUE INDEX IF NOT EXISTS uq_local_unit_photo_main ON local_unit_photo (fk_local_unit) WHERE type = 'MAIN';
CREATE UNIQUE INDEX IF NOT EXISTS uq_local_unit_photo_banner ON local_unit_photo (fk_local_unit) WHERE type = 'BANNER';
