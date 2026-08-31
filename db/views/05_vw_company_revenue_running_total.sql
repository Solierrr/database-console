-- View analitica de BI: faturamento mensal por empresa, com Running Total
-- (window function) do faturamento acumulado ao longo do tempo.

CREATE OR REPLACE VIEW vw_company_revenue_running_total AS
WITH monthly_revenue AS (
    SELECT
        f.company_key,
        dc.trade_name,
        date_trunc('month', f.date_key)::date AS revenue_month,
        SUM(f.line_total) AS revenue
    FROM fact_proposal_item f
    JOIN dim_company dc ON dc.company_key = f.company_key
    GROUP BY f.company_key, dc.trade_name, date_trunc('month', f.date_key)
)
SELECT
    company_key,
    trade_name,
    revenue_month,
    revenue,
    SUM(revenue) OVER (
        PARTITION BY company_key
        ORDER BY revenue_month
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_total_revenue
FROM monthly_revenue
ORDER BY company_key, revenue_month;
