-- Dominio de proposta (espelha api-core.proposal).

CREATE TABLE proposal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_requester UUID NOT NULL REFERENCES requester (id),
    status proposal_status NOT NULL DEFAULT 'AWAITING_SUPPLIER',
    notes TEXT,
    total_amount NUMERIC(12, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE proposal_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_proposal UUID NOT NULL REFERENCES proposal (id),
    fk_offer UUID NOT NULL REFERENCES offer (id),
    quantity INT NOT NULL,
    negotiated_price NUMERIC(12, 2),
    discount NUMERIC(5, 2)
);

CREATE TABLE proposal_unit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_proposal_item UUID NOT NULL REFERENCES proposal_item (id),
    fk_local_unit UUID NOT NULL REFERENCES local_unit (id),
    quantity INT NOT NULL,
    note TEXT
);
