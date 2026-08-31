-- Dimensao de empresa.

CREATE OR REPLACE VIEW dim_company AS
SELECT
    c.id AS company_key,
    c.trade_name,
    c.corporate_name,
    c.cnpj,
    c.status,
    c.business_type,
    a.city,
    a.state
FROM company c
LEFT JOIN address a ON a.id = c.fk_address;
