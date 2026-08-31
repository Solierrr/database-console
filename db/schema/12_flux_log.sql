-- Log de fluxo de acoes do usuario (espelha api-core.shared.FluxLog).

CREATE TABLE flux_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_user UUID NOT NULL REFERENCES users (id),
    action VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
