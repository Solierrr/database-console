<p align="center">
  <img src="../assets/readme/banners/postgresql.png" alt="PostgreSQL" width="100%">
</p>

# Otimização de consultas

As consultas do Data Mart foram analisadas com `EXPLAIN (ANALYZE, BUFFERS)` para decidir quais índices valem a pena. A análise foi feita numa cópia do `coredb` de QA, dentro de uma transação desfeita no fim, com massa sintética de 150 mil propostas e 150 mil itens para o planejador se comportar como em volume real.

## Método

1. Rodar a consulta com `EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)` e ler o nó mais caro: tipo de varredura, linhas lidas e buffers.
2. Criar o índice candidato e rodar `ANALYZE` na tabela, para as estatísticas refletirem o novo caminho.
3. Repetir a consulta e comparar o plano, os buffers e o tempo de execução.
4. Manter o índice só se o plano mudou e o ganho compensa o custo de escrita.

## Resultados

| Consulta | Antes | Depois | Plano depois |
|---|---|---|---|
| Propostas aceitas dos últimos 60 dias (`status` e `created_at`) | 62,1 ms, varredura sequencial paralela em `proposal` | 3,7 ms | `Index Scan using idx_proposal_status_created_at` |
| Valor aceito por mês (`bi.fact_proposta_item` com `bi.dim_tempo`) | 532,6 ms | 513,1 ms | Continua com varredura sequencial |

O índice `idx_proposal_status_created_at (status, created_at)` está em [`db/modelagem/80_indexes.sql`](../db/modelagem/80_indexes.sql).

## Leitura

- A consulta por situação e período lê só 2.797 das 150 mil linhas e passou a usar o índice. O ganho foi de 17 vezes.
- A agregação mensal precisa de cerca de 20% da tabela (todas as propostas aceitas de todo o histórico). Nesse caso o planejador prefere ler a tabela inteira, e o índice não ajuda. O caminho para essa consulta é materializar o resultado (uma view materializada atualizada em horário fixo) ou calculá-la no Databricks, não criar mais índices.
- As chaves estrangeiras de `proposal_item`, `order_item` e `charge` já têm índice no Flyway, então as junções dos fatos usam índice.

## Como repetir

1. Restaure uma cópia do banco ([`flows/RESTORE.md`](../flows/RESTORE.md)) e aplique `make modelagem-apply`.
2. Abra uma transação, carregue massa sintética e rode as consultas acima com `EXPLAIN (ANALYZE, BUFFERS)`.
3. Termine com `ROLLBACK` para não alterar o banco.

O custo de escrita do índice novo é pequeno: ele só cobre duas colunas de uma tabela com poucas atualizações por segundo.
