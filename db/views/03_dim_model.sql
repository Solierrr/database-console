-- Dimensao de produto (modelo de painel solar).

CREATE OR REPLACE VIEW dim_model AS
SELECT
    m.id AS model_key,
    m.brand,
    m.model,
    m.type,
    m.power_wp,
    m.efficiency,
    m.status
FROM model m;
