-- Fecha uma proposta (ACCEPTED ou REJECTED), validando a transicao de
-- estado e recalculando o total via fn_proposal_total.

CREATE OR REPLACE PROCEDURE sp_close_proposal(
    p_proposal_id UUID,
    p_new_status proposal_status
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_current_status proposal_status;
BEGIN
    IF p_new_status NOT IN ('ACCEPTED', 'REJECTED') THEN
        RAISE EXCEPTION 'sp_close_proposal so aceita ACCEPTED ou REJECTED, recebido: %', p_new_status;
    END IF;

    SELECT status INTO v_current_status FROM proposal WHERE id = p_proposal_id FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'proposta % nao encontrada', p_proposal_id;
    END IF;

    IF v_current_status IN ('ACCEPTED', 'REJECTED', 'CANCELED') THEN
        RAISE EXCEPTION 'proposta % ja esta fechada (status atual: %)', p_proposal_id, v_current_status;
    END IF;

    UPDATE proposal
    SET status = p_new_status,
        total_amount = fn_proposal_total(p_proposal_id),
        updated_at = now()
    WHERE id = p_proposal_id;
END;
$$;
