-- Calcula o valor total de uma proposta somando cada item
-- (preco negociado ou preco da oferta, com desconto aplicado).

CREATE OR REPLACE FUNCTION fn_proposal_total(p_proposal_id UUID)
RETURNS NUMERIC(14, 2)
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(SUM(
        pi.quantity * COALESCE(pi.negotiated_price, o.unit_price)
            * (1 - COALESCE(pi.discount, 0) / 100)
    ), 0)
    FROM proposal_item pi
    JOIN offer o ON o.id = pi.fk_offer
    WHERE pi.fk_proposal = p_proposal_id;
$$;
