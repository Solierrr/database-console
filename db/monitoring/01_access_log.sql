-- Log de acesso: uma linha por sessao de autenticacao criada, usada para
-- calcular DAU (Daily Active Users).

CREATE TABLE access_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_user UUID NOT NULL REFERENCES users (id),
    fk_session UUID REFERENCES auth_session (id),
    accessed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
