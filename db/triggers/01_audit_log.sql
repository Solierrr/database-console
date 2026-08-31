-- Tabela central de auditoria: uma linha por operacao de INSERT/UPDATE/
-- DELETE nas tabelas auditadas, guardando estado anterior/novo completo.

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    row_pk UUID,
    old_data JSONB,
    new_data JSONB,
    performed_by TEXT NOT NULL,
    performed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
