-- Auditoria por trigger. Cada INSERT, UPDATE e DELETE em purchase_order, offer e proposal
-- grava uma linha em audit.log com a operação (TG_OP), o usuário do banco (CURRENT_USER),
-- o usuário da sessão (SESSION_USER) e o estado antigo (OLD) e novo (NEW) da linha em JSON.

CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.log (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name text NOT NULL,
    operation text NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    row_id text,
    changed_by text NOT NULL,
    session_user_name text NOT NULL,
    changed_at timestamptz NOT NULL DEFAULT now(),
    old_data jsonb,
    new_data jsonb
);

CREATE INDEX IF NOT EXISTS idx_audit_log_table_changed_at ON audit.log (table_name, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_row ON audit.log (table_name, row_id);

CREATE OR REPLACE FUNCTION audit.fn_audit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit.log (table_name, operation, row_id, changed_by, session_user_name, new_data)
        VALUES (TG_TABLE_NAME, TG_OP, NEW.id::text, CURRENT_USER, SESSION_USER, to_jsonb(NEW));
    ELSIF TG_OP = 'UPDATE' THEN
        -- Atualizações que não mudam nada não geram linha de auditoria.
        IF to_jsonb(OLD) IS DISTINCT FROM to_jsonb(NEW) THEN
            INSERT INTO audit.log (table_name, operation, row_id, changed_by, session_user_name, old_data, new_data)
            VALUES (TG_TABLE_NAME, TG_OP, NEW.id::text, CURRENT_USER, SESSION_USER, to_jsonb(OLD), to_jsonb(NEW));
        END IF;
    ELSE
        INSERT INTO audit.log (table_name, operation, row_id, changed_by, session_user_name, old_data)
        VALUES (TG_TABLE_NAME, TG_OP, OLD.id::text, CURRENT_USER, SESSION_USER, to_jsonb(OLD));
    END IF;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE TRIGGER trg_audit_purchase_order
AFTER INSERT OR UPDATE OR DELETE ON purchase_order
FOR EACH ROW EXECUTE FUNCTION audit.fn_audit();

CREATE OR REPLACE TRIGGER trg_audit_offer
AFTER INSERT OR UPDATE OR DELETE ON offer
FOR EACH ROW EXECUTE FUNCTION audit.fn_audit();

CREATE OR REPLACE TRIGGER trg_audit_proposal
AFTER INSERT OR UPDATE OR DELETE ON proposal
FOR EACH ROW EXECUTE FUNCTION audit.fn_audit();
