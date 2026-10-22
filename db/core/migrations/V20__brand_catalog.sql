CREATE TABLE brand (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_owner_company UUID,
    name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    visibility VARCHAR(16) NOT NULL DEFAULT 'PRIVATE' CHECK (visibility IN ('PRIVATE','PUBLIC')),
    archived BOOLEAN NOT NULL DEFAULT false,
    legacy BOOLEAN NOT NULL DEFAULT false,
    logo_url VARCHAR(2048), reference_url VARCHAR(2048),
    revision BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_brand_public_active CHECK (visibility <> 'PUBLIC' OR NOT archived),
    CONSTRAINT ck_brand_owner CHECK (fk_owner_company IS NOT NULL OR legacy OR visibility = 'PUBLIC')
);
CREATE UNIQUE INDEX uq_brand_public_name ON brand(normalized_name) WHERE visibility = 'PUBLIC';
CREATE UNIQUE INDEX uq_brand_private_company_name ON brand(fk_owner_company,normalized_name) WHERE visibility = 'PRIVATE' AND NOT archived;
CREATE TABLE brand_request (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_brand UUID NOT NULL REFERENCES brand(id),
    fk_requester_company UUID REFERENCES company(id), fk_requester_user UUID REFERENCES users(id),
    kind VARCHAR(16) NOT NULL CHECK (kind IN ('PUBLICATION','CORRECTION')),
    status VARCHAR(16) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','REJECTED','CANCELLED')),
    proposed_name VARCHAR(255) NOT NULL, proposed_logo_url VARCHAR(2048), proposed_reference_url VARCHAR(2048),
    fk_result_brand UUID REFERENCES brand(id), decision_reason VARCHAR(2000),
    fk_decided_by UUID REFERENCES users(id), decided_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revision BIGINT NOT NULL DEFAULT 0,
    CONSTRAINT ck_brand_rejection_reason CHECK (status <> 'REJECTED' OR length(trim(decision_reason)) > 0 AND decision_reason IS NOT NULL)
);
CREATE UNIQUE INDEX uq_brand_pending_request ON brand_request(fk_brand) WHERE status = 'PENDING';
CREATE INDEX ix_brand_request_company ON brand_request(fk_requester_company, created_at DESC);
ALTER TABLE brand ADD CONSTRAINT fk_brand_owner_company FOREIGN KEY (fk_owner_company) REFERENCES company(id);

INSERT INTO brand(name,normalized_name,legacy)
SELECT min(trim(brand)),lower(regexp_replace(trim(brand),'\s+',' ','g')),true FROM model
GROUP BY lower(regexp_replace(trim(brand),'\s+',' ','g'));
ALTER TABLE model ADD COLUMN fk_brand UUID;
UPDATE model m SET fk_brand=b.id FROM brand b WHERE b.normalized_name=lower(regexp_replace(trim(m.brand),'\s+',' ','g')) AND b.legacy;
ALTER TABLE model ALTER COLUMN fk_brand SET NOT NULL;
ALTER TABLE model ADD CONSTRAINT fk_model_brand FOREIGN KEY (fk_brand) REFERENCES brand(id);
INSERT INTO brand_request(fk_brand,kind,proposed_name)
SELECT id,'PUBLICATION',name FROM brand WHERE legacy;
ALTER TABLE model DROP COLUMN brand;
