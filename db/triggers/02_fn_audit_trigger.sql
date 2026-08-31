-- Funcao de trigger generica de auditoria: registra TG_OP, NEW/OLD (como
-- jsonb) e CURRENT_USER para qualquer tabela em que for anexada.

CREATE OR REPLACE FUNCTION fn_audit_trigger()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO audit_log (table_name, operation, row_pk, old_data, new_data, performed_by)
    VALUES (
        TG_TABLE_NAME,
        TG_OP,
        COALESCE(NEW.id, OLD.id),
        CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN to_jsonb(OLD) END,
        CASE WHEN TG_OP IN ('UPDATE', 'INSERT') THEN to_jsonb(NEW) END,
        CURRENT_USER
    );
    RETURN COALESCE(NEW, OLD);
END;
$$;
