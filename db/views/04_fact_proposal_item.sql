-- Fato: item de proposta (grain = 1 linha por proposal_item). Star schema
-- com dim_company, dim_model e dim_date.

CREATE OR REPLACE VIEW fact_proposal_item AS
SELECT
    pi.id AS proposal_item_key,
    p.id AS proposal_key,
    c.id AS company_key,
    m.id AS model_key,
    p.created_at::date AS date_key,
    p.status AS proposal_status,
    pi.quantity,
    o.unit_price,
    pi.negotiated_price,
    COALESCE(pi.discount, 0) AS discount_pct,
    pi.quantity * COALESCE(pi.negotiated_price, o.unit_price)
        * (1 - COALESCE(pi.discount, 0) / 100) AS line_total
FROM proposal_item pi
JOIN proposal p ON p.id = pi.fk_proposal
JOIN requester r ON r.id = p.fk_requester
JOIN company c ON c.id = r.fk_company
JOIN offer o ON o.id = pi.fk_offer
JOIN model m ON m.id = o.fk_model;
