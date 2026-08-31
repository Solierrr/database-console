-- Estrutura avancada: CTE recursiva percorrendo a cadeia de rotacao de
-- refresh tokens (refresh_token.fk_replaced_by referencia a proxima
-- geracao do mesmo token). Util para investigar reuso de token roubado
-- (SecurityEventType.REFRESH_TOKEN_REUSED).

CREATE OR REPLACE FUNCTION fn_refresh_token_lineage(p_token_id UUID)
RETURNS TABLE (
    id UUID,
    depth INT,
    fk_session UUID,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ
)
LANGUAGE sql
STABLE
AS $$
    WITH RECURSIVE lineage AS (
        SELECT rt.id, 0 AS depth, rt.fk_session, rt.revoked_at, rt.created_at, rt.fk_replaced_by
        FROM refresh_token rt
        WHERE rt.id = p_token_id

        UNION ALL

        SELECT rt.id, lineage.depth + 1, rt.fk_session, rt.revoked_at, rt.created_at, rt.fk_replaced_by
        FROM refresh_token rt
        JOIN lineage ON rt.id = lineage.fk_replaced_by
    )
    SELECT lineage.id, lineage.depth, lineage.fk_session, lineage.revoked_at, lineage.created_at
    FROM lineage
    ORDER BY depth;
$$;
