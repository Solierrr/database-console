-- Dominio de unidade local (espelha api-core.unit).

CREATE TABLE local_unit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_requester UUID NOT NULL REFERENCES requester (id),
    fk_address UUID REFERENCES address (id),
    complement VARCHAR(255),
    location_type location_type NOT NULL
);

-- Subtype 1:1 de media_asset.
CREATE TABLE local_unit_photo (
    id UUID PRIMARY KEY REFERENCES media_asset (id) ON DELETE CASCADE,
    fk_local_unit UUID NOT NULL REFERENCES local_unit (id)
);

CREATE TABLE unit_specifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_local_unit UUID NOT NULL REFERENCES local_unit (id),
    specifications TEXT,
    location_photos TEXT,
    date TIMESTAMPTZ NOT NULL
);

CREATE TABLE energy_bill (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_local_unit UUID NOT NULL REFERENCES local_unit (id),
    consumption NUMERIC(10, 2) NOT NULL,
    price NUMERIC(12, 2) NOT NULL,
    photo_url TEXT,
    photo_public_id VARCHAR(255)
);
