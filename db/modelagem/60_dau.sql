-- Monitoramento de DAU (Daily Active User) direto no banco do api-auth.
-- Cada nova sessão (auth_session) conta como um acesso do usuário naquele dia, no fuso de São Paulo.
-- O registro é feito por trigger: o api-auth não precisa mudar e nenhum acesso fica sem registro.

CREATE SCHEMA IF NOT EXISTS monitoring;

CREATE TABLE IF NOT EXISTS monitoring.daily_active_user (
    day date NOT NULL,
    auth_user_id uuid NOT NULL,
    first_access_at timestamptz NOT NULL,
    last_access_at timestamptz NOT NULL,
    session_count integer NOT NULL DEFAULT 1,
    PRIMARY KEY (day, auth_user_id)
);

COMMENT ON TABLE monitoring.daily_active_user IS 'Um registro por usuário e dia com ao menos uma sessão criada.';

CREATE OR REPLACE FUNCTION monitoring.fn_register_dau()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO monitoring.daily_active_user (day, auth_user_id, first_access_at, last_access_at)
    VALUES ((NEW.created_at AT TIME ZONE 'America/Sao_Paulo')::date, NEW.auth_user_id, NEW.created_at, NEW.created_at)
    ON CONFLICT (day, auth_user_id) DO UPDATE
    SET last_access_at = GREATEST(monitoring.daily_active_user.last_access_at, EXCLUDED.last_access_at),
        session_count = monitoring.daily_active_user.session_count + 1;
    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    -- Monitoramento nunca pode impedir um login.
    RAISE WARNING 'DAU não registrado para a sessão %: %', NEW.id, SQLERRM;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER trg_auth_session_dau
AFTER INSERT ON auth_session
FOR EACH ROW EXECUTE FUNCTION monitoring.fn_register_dau();

-- Carga do histórico que já existia antes do trigger.
INSERT INTO monitoring.daily_active_user (day, auth_user_id, first_access_at, last_access_at, session_count)
SELECT (created_at AT TIME ZONE 'America/Sao_Paulo')::date,
       auth_user_id,
       MIN(created_at),
       MAX(created_at),
       COUNT(*)
FROM auth_session
GROUP BY 1, 2
ON CONFLICT (day, auth_user_id) DO NOTHING;

-- Usuários ativos por dia, com a média móvel de 7 dias.
CREATE OR REPLACE VIEW monitoring.vw_dau AS
WITH diario AS (
    SELECT day,
           COUNT(*) AS active_users,
           SUM(session_count) AS sessions
    FROM monitoring.daily_active_user
    GROUP BY day
)
SELECT day,
       active_users,
       sessions,
       ROUND(AVG(active_users) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS active_users_avg_7d
FROM diario;
