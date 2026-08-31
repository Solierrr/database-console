-- Dimensao de tempo (calendario) para o data mart, gerada sob demanda via
-- generate_series -- nao ha necessidade de persistir como tabela no
-- volume deste projeto.

CREATE OR REPLACE VIEW dim_date AS
SELECT
    d::date AS date_key,
    EXTRACT(YEAR FROM d)::INT AS year,
    EXTRACT(MONTH FROM d)::INT AS month,
    EXTRACT(DAY FROM d)::INT AS day,
    EXTRACT(QUARTER FROM d)::INT AS quarter,
    TO_CHAR(d, 'YYYY-MM') AS year_month,
    TRIM(TO_CHAR(d, 'Day')) AS weekday_name
FROM generate_series(DATE '2015-01-01', DATE '2035-12-31', INTERVAL '1 day') AS d;
