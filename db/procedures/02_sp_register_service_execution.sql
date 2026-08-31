-- Registra um executor (tecnico afiliado) em um servico tecnico e, se o
-- servico ainda estiver OPEN, avanca o status para IN_PROGRESS.

CREATE OR REPLACE PROCEDURE sp_register_service_execution(
    p_service_id UUID,
    p_technician_affiliation_id UUID,
    p_function VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_current_status service_status;
BEGIN
    SELECT status INTO v_current_status FROM technical_service WHERE id = p_service_id FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'servico tecnico % nao encontrado', p_service_id;
    END IF;

    IF v_current_status = 'CANCELED' OR v_current_status = 'COMPLETED' THEN
        RAISE EXCEPTION 'nao e possivel registrar executor em servico com status %', v_current_status;
    END IF;

    INSERT INTO service_executor (fk_service, fk_technician_affiliation, function)
    VALUES (p_service_id, p_technician_affiliation_id, p_function);

    IF v_current_status = 'OPEN' THEN
        UPDATE technical_service SET status = 'IN_PROGRESS' WHERE id = p_service_id;
    END IF;
END;
$$;
