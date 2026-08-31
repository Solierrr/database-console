-- Verifica se alguma das assinaturas dos suppliers de uma empresa esta
-- ativa (paga e ainda dentro do periodo de vigencia).

CREATE OR REPLACE FUNCTION fn_company_has_active_subscription(p_company_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM subscription s
        JOIN supplier sup ON sup.id = s.fk_supplier
        WHERE sup.fk_company = p_company_id
          AND s.status = 'PAID'
          AND (s.end_date IS NULL OR s.end_date > now())
    );
$$;
