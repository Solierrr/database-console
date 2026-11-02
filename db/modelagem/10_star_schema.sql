-- Data Mart do coredb em esquema estrela (Star Schema), para ferramentas de BI.
-- As dimensões descrevem quem, o quê e quando; os fatos guardam as medidas.
-- Origem: tabelas do Flyway do api-core. Idempotente (CREATE OR REPLACE).

CREATE SCHEMA IF NOT EXISTS bi;

-- Dimensão tempo: um dia por linha, do primeiro ao último evento de negócio.
CREATE OR REPLACE VIEW bi.dim_tempo AS
WITH eventos AS (
    SELECT created_at::date AS dia FROM proposal
    UNION ALL
    SELECT created_at::date FROM purchase_order
    UNION ALL
    SELECT due_date FROM charge
),
limites AS (
    SELECT MIN(dia) AS inicio, MAX(dia) AS fim FROM eventos
),
dias AS (
    SELECT generate_series(inicio, fim, interval '1 day')::date AS dia FROM limites
)
SELECT to_char(dia, 'YYYYMMDD')::int AS sk_tempo,
       dia,
       EXTRACT(year FROM dia)::int AS ano,
       EXTRACT(quarter FROM dia)::int AS trimestre,
       EXTRACT(month FROM dia)::int AS mes,
       to_char(dia, 'YYYY-MM') AS ano_mes,
       EXTRACT(isodow FROM dia)::int AS dia_da_semana
FROM dias;

-- Dimensão fornecedor: empresa fornecedora com o tipo de negócio e a localização.
CREATE OR REPLACE VIEW bi.dim_fornecedor AS
WITH base AS (
    SELECT s.id AS fornecedor_id,
           c.trade_name AS nome_fantasia,
           s.business_type AS tipo_negocio,
           s.status AS situacao,
           a.state AS estado,
           a.city AS cidade
    FROM supplier s
    JOIN company c ON c.id = s.company_id
    LEFT JOIN address a ON a.id = c.address_id
)
SELECT * FROM base;

-- Dimensão demandante: empresa que compra ou pede propostas.
CREATE OR REPLACE VIEW bi.dim_demandante AS
WITH base AS (
    SELECT r.id AS demandante_id,
           c.trade_name AS nome_fantasia,
           r.business_type AS tipo_negocio,
           a.state AS estado,
           a.city AS cidade
    FROM requester r
    JOIN company c ON c.id = r.company_id
    LEFT JOIN address a ON a.id = c.address_id
)
SELECT * FROM base;

-- Dimensão modelo: o painel solar com a marca e as características técnicas.
CREATE OR REPLACE VIEW bi.dim_modelo AS
WITH base AS (
    SELECT m.id AS modelo_id,
           m.model_name AS modelo,
           b.name AS marca,
           m.power_wp AS potencia_wp,
           m.efficiency AS eficiencia,
           m.type AS tipo_painel,
           m.status AS situacao
    FROM model m
    JOIN brand b ON b.id = m.brand_id
)
SELECT * FROM base;

-- Fato proposta: um item de proposta por linha. Valor = preço negociado × quantidade,
-- sem aplicar o desconto uma segunda vez (o preço negociado já o inclui).
CREATE OR REPLACE VIEW bi.fact_proposta_item AS
WITH itens AS (
    SELECT pi.id AS proposta_item_id,
           p.id AS proposta_id,
           p.created_at::date AS dia,
           p.supplier_id AS fornecedor_id,
           p.requester_id AS demandante_id,
           o.model_id AS modelo_id,
           p.status AS situacao,
           pi.quantity AS quantidade,
           pi.negotiated_unit_price AS preco_negociado,
           pi.discount AS desconto
    FROM proposal_item pi
    JOIN proposal p ON p.id = pi.proposal_id
    JOIN offer o ON o.id = pi.offer_id
)
SELECT proposta_item_id,
       proposta_id,
       to_char(dia, 'YYYYMMDD')::int AS sk_tempo,
       fornecedor_id,
       demandante_id,
       modelo_id,
       situacao,
       quantidade,
       preco_negociado,
       desconto,
       quantidade * preco_negociado AS valor_total
FROM itens;

-- Fato pedido: um item de pedido de compra por linha.
CREATE OR REPLACE VIEW bi.fact_pedido_item AS
WITH itens AS (
    SELECT oi.id AS pedido_item_id,
           po.id AS pedido_id,
           po.created_at::date AS dia,
           oi.supplier_id AS fornecedor_id,
           o.model_id AS modelo_id,
           po.status AS situacao,
           oi.quantity AS quantidade,
           oi.net_unit_price AS preco_liquido,
           oi.line_total_amount AS valor_total
    FROM order_item oi
    JOIN purchase_order po ON po.id = oi.purchase_order_id
    LEFT JOIN offer o ON o.id = oi.offer_id
)
SELECT pedido_item_id,
       pedido_id,
       to_char(dia, 'YYYYMMDD')::int AS sk_tempo,
       fornecedor_id,
       modelo_id,
       situacao,
       quantidade,
       preco_liquido,
       valor_total
FROM itens;

-- Fato cobrança: uma cobrança de assinatura por linha, no dia do vencimento.
CREATE OR REPLACE VIEW bi.fact_cobranca AS
WITH cobrancas AS (
    SELECT ch.id AS cobranca_id,
           ch.due_date AS dia,
           s.supplier_id AS fornecedor_id,
           s.company_plan_id AS plano_id,
           ch.status AS situacao,
           ch.payment_method AS forma_pagamento,
           ch.amount AS valor,
           (ch.paid_at IS NOT NULL) AS pago
    FROM charge ch
    JOIN subscription s ON s.id = ch.subscription_id
)
SELECT cobranca_id,
       to_char(dia, 'YYYYMMDD')::int AS sk_tempo,
       fornecedor_id,
       plano_id,
       situacao,
       forma_pagamento,
       valor,
       pago
FROM cobrancas;
