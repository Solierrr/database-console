-- Rede de conexões entre usuários com CTE recursiva.
-- user_account.connection_user_ids guarda as conexões diretas de cada usuário. A consulta
-- caminha pela rede até 3 graus de distância e evita ciclos guardando o caminho percorrido.

CREATE OR REPLACE VIEW bi.vw_rede_conexoes AS
WITH RECURSIVE arestas AS (
    SELECT u.id AS origem_id,
           conexao AS destino_id
    FROM user_account u
    CROSS JOIN LATERAL unnest(u.connection_user_ids) AS conexao
),
caminhos (raiz_id, usuario_id, grau, caminho) AS (
    SELECT u.id, u.id, 0, ARRAY[u.id]
    FROM user_account u
    UNION ALL
    SELECT c.raiz_id,
           a.destino_id,
           c.grau + 1,
           c.caminho || a.destino_id
    FROM caminhos c
    JOIN arestas a ON a.origem_id = c.usuario_id
    WHERE a.destino_id <> ALL (c.caminho)
      AND c.grau < 3
)
SELECT raiz_id,
       usuario_id,
       MIN(grau) AS grau
FROM caminhos
WHERE grau > 0
GROUP BY raiz_id, usuario_id;

-- Alcance de cada usuário: quantas pessoas ele alcança em cada grau.
CREATE OR REPLACE VIEW bi.vw_alcance_conexoes AS
WITH por_grau AS (
    SELECT raiz_id,
           grau,
           COUNT(*) AS pessoas
    FROM bi.vw_rede_conexoes
    GROUP BY raiz_id, grau
)
SELECT raiz_id,
       grau,
       pessoas,
       SUM(pessoas) OVER (PARTITION BY raiz_id ORDER BY grau) AS pessoas_acumuladas
FROM por_grau;
