-- Functions e Procedures de regras de negócio do coredb (schema regras).
-- As regras ficam no banco para valerem para qualquer cliente que escreva nele.

CREATE SCHEMA IF NOT EXISTS regras;

-- Function: valor de uma proposta = soma de preço negociado × quantidade dos itens.
-- Devolve NULL enquanto algum item ainda não tem preço negociado, porque o valor ainda não existe.
CREATE OR REPLACE FUNCTION regras.valor_proposta(p_proposta_id uuid)
RETURNS numeric
LANGUAGE sql
STABLE
AS $$
    SELECT CASE WHEN COUNT(*) = 0 OR COUNT(*) FILTER (WHERE pi.negotiated_unit_price IS NULL) > 0
                THEN NULL
                ELSE SUM(pi.quantity * pi.negotiated_unit_price)
           END
    FROM proposal_item pi
    WHERE pi.proposal_id = p_proposta_id
$$;

-- Function: taxa de aceite de um fornecedor, em %, entre as propostas já encerradas
-- (aceitas, recusadas ou canceladas). Sem propostas encerradas, devolve 0.
CREATE OR REPLACE FUNCTION regras.taxa_aceite(p_fornecedor_id uuid)
RETURNS numeric
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        ROUND(
            100.0 * COUNT(*) FILTER (WHERE status = 'ACCEPTED')
            / NULLIF(COUNT(*) FILTER (WHERE status IN ('ACCEPTED', 'REJECTED', 'CANCELED')), 0),
            2),
        0)
    FROM proposal
    WHERE supplier_id = p_fornecedor_id
$$;

-- Procedure: recalcula o total de uma proposta a partir dos itens negociados.
-- Falha se a proposta não existir; só grava quando o total muda. Se a proposta não tem itens ou
-- algum item ainda não tem preço negociado, o total informado é mantido, porque não há de onde recalcular.
CREATE OR REPLACE PROCEDURE regras.recalcular_total_proposta(p_proposta_id uuid)
LANGUAGE plpgsql
AS $$
DECLARE
    v_total numeric;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM proposal WHERE id = p_proposta_id) THEN
        RAISE EXCEPTION 'Proposta % não existe', p_proposta_id USING ERRCODE = 'P0002';
    END IF;

    v_total := regras.valor_proposta(p_proposta_id);

    IF v_total IS NULL THEN
        RAISE NOTICE 'Proposta % sem itens negociados; o total foi mantido', p_proposta_id;
        RETURN;
    END IF;

    UPDATE proposal
    SET total_amount = v_total,
        updated_at = now()
    WHERE id = p_proposta_id
      AND total_amount IS DISTINCT FROM v_total;
END;
$$;

-- Procedure: cancela as propostas que ficaram aguardando resposta por mais de p_dias dias.
-- Devolve em p_canceladas quantas foram canceladas.
CREATE OR REPLACE PROCEDURE regras.cancelar_propostas_paradas(p_dias integer, INOUT p_canceladas integer DEFAULT 0)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_dias IS NULL OR p_dias < 1 THEN
        RAISE EXCEPTION 'p_dias deve ser maior ou igual a 1' USING ERRCODE = '22023';
    END IF;

    UPDATE proposal
    SET status = 'CANCELED',
        updated_at = now()
    WHERE status IN ('AWAITING_SUPPLIER', 'AWAITING_REQUESTER')
      AND updated_at < now() - make_interval(days => p_dias);

    GET DIAGNOSTICS p_canceladas = ROW_COUNT;
END;
$$;
