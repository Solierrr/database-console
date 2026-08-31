-- Dominio profissional (espelha api-core.professional).

CREATE TABLE profession (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100),
    accept_emergency_call BOOLEAN NOT NULL DEFAULT FALSE,
    requires_registration BOOLEAN
);

CREATE TABLE certification (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100),
    issuer VARCHAR(100),
    validity TIMESTAMP,
    description TEXT
);

CREATE TABLE technician (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_person UUID NOT NULL REFERENCES person (id),
    crea VARCHAR(60) NOT NULL,
    slug VARCHAR(160) NOT NULL UNIQUE
);

CREATE TABLE professional_registration (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_technician UUID REFERENCES technician (id),
    fk_profession UUID REFERENCES profession (id),
    council VARCHAR(60),
    number VARCHAR(30),
    expiration_date TIMESTAMP
);

CREATE TABLE certification_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_professional_registration UUID REFERENCES professional_registration (id),
    fk_certification UUID REFERENCES certification (id)
);

CREATE TABLE technician_affiliation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_company UUID REFERENCES company (id),
    fk_technician UUID NOT NULL REFERENCES technician (id),
    affiliation_type technical_affiliation_type NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE shift (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_technician UUID NOT NULL REFERENCES technician (id),
    day_week day_week NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL
);

CREATE TABLE technical_course (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_company UUID REFERENCES company (id),
    title VARCHAR(120),
    information TEXT,
    link TEXT
);

-- fk_service (technical_service) e adicionada via ALTER em 08_execution.sql
CREATE TABLE professional_review (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_professional UUID NOT NULL REFERENCES technician (id),
    fk_reviewer UUID NOT NULL REFERENCES users (id),
    fk_service UUID NOT NULL,
    rating NUMERIC(2, 1) NOT NULL CHECK (rating BETWEEN 0 AND 5),
    comment TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (fk_reviewer, fk_professional, fk_service)
);
