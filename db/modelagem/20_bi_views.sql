-- Views analíticas sobre o esquema estrela. Usam CTEs para organizar a transformação
-- e funções de janela (Window Functions) para acumulados, variações e rankings.

-- Valor aceito por mês, com total acumulado (Running Total), variação e média móvel de 3 meses.
CREATE OR REPLACE VIEW bi.vw_valor_aceito_mensal AS
WITH mensal AS (
    SELECT t.ano_mes,
           COUNT(DISTINCT f.proposta_id) AS propostas,
           SUM(f.valor_total) AS valor_aceito
    FROM bi.fact_proposta_item f
    JOIN bi.dim_tempo t ON t.sk_tempo = f.sk_tempo
    WHERE f.situacao = 'ACCEPTED'
    GROUP BY t.ano_mes
)
SELECT ano_mes,
       propostas,
       valor_aceito,
       SUM(valor_aceito) OVER (ORDER BY ano_mes) AS valor_acumulado,
       valor_aceito - LAG(valor_aceito) OVER (ORDER BY ano_mes) AS variacao_mensal,
       ROUND(AVG(valor_aceito) OVER (ORDER BY ano_mes ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS media_movel_3m
FROM mensal;

-- Ranking de fornecedores pelo valor aceito: geral e dentro do estado, com a participação no total.
CREATE OR REPLACE VIEW bi.vw_ranking_fornecedores AS
WITH por_fornecedor AS (
    SELECT d.fornecedor_id,
           d.nome_fantasia,
           d.estado,
           SUM(f.valor_total) AS valor_aceito,
           SUM(f.quantidade) AS unidades
    FROM bi.fact_proposta_item f
    JOIN bi.dim_fornecedor d ON d.fornecedor_id = f.fornecedor_id
    WHERE f.situacao = 'ACCEPTED'
    GROUP BY d.fornecedor_id, d.nome_fantasia, d.estado
)
SELECT fornecedor_id,
       nome_fantasia,
       estado,
       valor_aceito,
       unidades,
       RANK() OVER (ORDER BY valor_aceito DESC) AS posicao_geral,
       RANK() OVER (PARTITION BY estado ORDER BY valor_aceito DESC) AS posicao_no_estado,
       ROUND(100 * valor_aceito / SUM(valor_aceito) OVER (), 2) AS participacao_pct
FROM por_fornecedor;

-- Ranking de modelos por unidades vendidas dentro de cada marca.
CREATE OR REPLACE VIEW bi.vw_ranking_modelos AS
WITH por_modelo AS (
    SELECT m.modelo_id,
           m.marca,
           m.modelo,
           SUM(f.quantidade) AS unidades,
           SUM(f.valor_total) AS valor_aceito
    FROM bi.fact_proposta_item f
    JOIN bi.dim_modelo m ON m.modelo_id = f.modelo_id
    WHERE f.situacao = 'ACCEPTED'
    GROUP BY m.modelo_id, m.marca, m.modelo
)
SELECT modelo_id,
       marca,
       modelo,
       unidades,
       valor_aceito,
       DENSE_RANK() OVER (PARTITION BY marca ORDER BY unidades DESC) AS posicao_na_marca,
       ROUND(valor_aceito / NULLIF(unidades, 0), 2) AS preco_medio
FROM por_modelo;

-- Receita de assinaturas por mês, com o total acumulado.
CREATE OR REPLACE VIEW bi.vw_receita_assinaturas_mensal AS
WITH mensal AS (
    SELECT t.ano_mes,
           SUM(c.valor) FILTER (WHERE c.pago) AS recebido,
           SUM(c.valor) AS faturado
    FROM bi.fact_cobranca c
    JOIN bi.dim_tempo t ON t.sk_tempo = c.sk_tempo
    GROUP BY t.ano_mes
)
SELECT ano_mes,
       faturado,
       COALESCE(recebido, 0) AS recebido,
       SUM(COALESCE(recebido, 0)) OVER (ORDER BY ano_mes) AS recebido_acumulado
FROM mensal;
