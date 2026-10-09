-- Review ambiguous historical companies before applying this migration.
ALTER TABLE company ADD COLUMN IF NOT EXISTS type VARCHAR(16);
ALTER TABLE company ADD COLUMN IF NOT EXISTS slug VARCHAR(160);
ALTER TABLE company ALTER COLUMN fk_address DROP NOT NULL;
ALTER TABLE company ALTER COLUMN fk_business_contact DROP NOT NULL;

UPDATE company SET slug = 'empresa-' || replace(id::text, '-', '') WHERE slug IS NULL;
ALTER TABLE company ALTER COLUMN slug SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_company_slug_unique ON company (slug);

INSERT INTO position (name, accesses)
SELECT 'ADMIN', ''
WHERE NOT EXISTS (SELECT 1 FROM position WHERE name = 'ADMIN');

CREATE UNIQUE INDEX IF NOT EXISTS idx_position_name_unique ON position (name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_company_user_unique ON user_company (fk_users);

UPDATE company c
SET type = CASE
    WHEN EXISTS (SELECT 1 FROM supplier s WHERE s.fk_company = c.id)
     AND NOT EXISTS (SELECT 1 FROM requester r WHERE r.fk_company = c.id)
        THEN 'SUPPLIER'
    WHEN EXISTS (SELECT 1 FROM requester r WHERE r.fk_company = c.id)
     AND NOT EXISTS (SELECT 1 FROM supplier s WHERE s.fk_company = c.id)
        THEN 'DEMANDANT'
    ELSE NULL
END
WHERE c.type IS NULL;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM company WHERE type IS NULL) THEN
        RAISE EXCEPTION 'Company type is ambiguous or missing; review supplier/requester associations before continuing';
    END IF;
END $$;

ALTER TABLE company ALTER COLUMN type SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'company_type_check') THEN
        ALTER TABLE company ADD CONSTRAINT company_type_check CHECK (type IN ('SUPPLIER', 'DEMANDANT'));
    END IF;
END $$;

-- Audit historical companies without an Admin owner. Ownership cannot be
-- inferred safely from the company record.
SELECT c.id, c.trade_name
FROM company c
WHERE NOT EXISTS (
    SELECT 1
    FROM user_company uc
    JOIN position p ON p.id = uc.fk_position
    WHERE uc.fk_company = c.id AND p.name = 'ADMIN'
);
