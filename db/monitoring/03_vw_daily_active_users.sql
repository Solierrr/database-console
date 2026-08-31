-- DAU (Daily Active Users) por dia, com media movel de 7 dias
-- (window function) para suavizar tendencia.

CREATE OR REPLACE VIEW vw_daily_active_users AS
WITH daily AS (
    SELECT
        accessed_at::date AS access_date,
        COUNT(DISTINCT fk_user) AS dau
    FROM access_log
    GROUP BY accessed_at::date
)
SELECT
    access_date,
    dau,
    ROUND(AVG(dau) OVER (
        ORDER BY access_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 2) AS dau_7d_avg
FROM daily
ORDER BY access_date;
