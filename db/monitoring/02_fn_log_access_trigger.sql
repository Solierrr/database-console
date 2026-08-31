-- Trigger que registra automaticamente em access_log toda vez que uma
-- nova sessao de autenticacao e criada (login bem-sucedido).

CREATE OR REPLACE FUNCTION fn_log_access()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id UUID;
BEGIN
    SELECT id INTO v_user_id FROM users WHERE fk_auth_user = NEW.fk_user;

    IF v_user_id IS NOT NULL THEN
        INSERT INTO access_log (fk_user, fk_session, accessed_at)
        VALUES (v_user_id, NEW.id, NEW.created_at);
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_log_access
AFTER INSERT ON auth_session
FOR EACH ROW EXECUTE FUNCTION fn_log_access();
