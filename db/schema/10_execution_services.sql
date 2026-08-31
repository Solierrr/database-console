-- Dominio de execucao, parte 2 (projeto/servico/contrato/executor).

CREATE TABLE technical_project (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_requester UUID REFERENCES requester (id),
    fk_local_unit UUID REFERENCES local_unit (id),
    status service_status,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMP
);

CREATE TABLE technical_service (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_technical_project UUID NOT NULL REFERENCES technical_project (id),
    purpose VARCHAR(255) NOT NULL,
    status service_status NOT NULL DEFAULT 'OPEN',
    scheduled_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    fk_accepted_by UUID REFERENCES users (id),
    accepted_at TIMESTAMPTZ,
    end_date TIMESTAMPTZ
);

ALTER TABLE professional_review
    ADD CONSTRAINT fk_professional_review_service FOREIGN KEY (fk_service) REFERENCES technical_service (id);

CREATE TABLE service_contract (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_service UUID NOT NULL UNIQUE REFERENCES technical_service (id),
    warranty VARCHAR(255),
    delivery_deadline DATE,
    insurance BOOLEAN NOT NULL DEFAULT FALSE,
    utility_approval BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE service_executor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_service UUID NOT NULL REFERENCES technical_service (id),
    fk_technician_affiliation UUID NOT NULL REFERENCES technician_affiliation (id),
    function VARCHAR(120) NOT NULL
);
