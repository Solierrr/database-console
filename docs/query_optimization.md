# Otimização de consultas (EXPLAIN ANALYZE)

Medições reais feitas localmente (Postgres 18) com o schema completo
aplicado e ~35 mil linhas carregadas (`--rows 30000`, escala usada só
para gerar volume suficiente para o planner preferir index scan — o
dataload padrão do projeto é `--rows 1000`). Os índices avaliados estão
em [`db/indexes/01_performance_indexes.sql`](../db/indexes/01_performance_indexes.sql).

## 1. Itens de uma proposta (`proposal_item.fk_proposal`)

Consulta: buscar os itens de uma proposta específica — o caminho mais
comum ao abrir o detalhe de uma proposta.

| | Antes (Seq Scan) | Depois (`idx_proposal_item_fk_proposal`) |
|---|---|---|
| Plano | `Seq Scan on proposal_item`, 9032 linhas descartadas | `Bitmap Index Scan` |
| Execution Time | 0.877 ms | 0.144 ms |

~6x mais rápido; a diferença cresce com o volume de `proposal_item`.

## 2. Eventos de segurança por usuário (`security_event.fk_user, occurred_at`)

Consulta: histórico de eventos de segurança de um usuário, ordenado do
mais recente (tela de "atividade da conta").

| | Antes | Depois (`idx_security_event_fk_user_occurred_at`) |
|---|---|---|
| Plano | `Seq Scan` + `Sort` | `Bitmap Index Scan` já ordenado pela definição do índice (`fk_user, occurred_at DESC`) |
| Execution Time | 1.740 ms | 0.148 ms |

~11x mais rápido — o índice composto evita o sort explícito além de
evitar a varredura completa.

## 3. Ofertas de um fornecedor (`offer.fk_supplier`)

| | Antes | Depois (`idx_offer_fk_supplier`) |
|---|---|---|
| Execution Time | 0.660 ms | 0.128 ms |

~5x mais rápido.

## 4. Propostas por status (`proposal.status`)

| | Antes | Depois (`idx_proposal_status`) |
|---|---|---|
| Execution Time | 0.949 ms | 0.469 ms |

Só ~2x — ganho real, porém menor que os anteriores. `ACCEPTED`
corresponde a ~20% das linhas nesta carga (baixa seletividade), então o
Bitmap Heap Scan ainda revisita boa parte das páginas da tabela. Esse é
o comportamento esperado: índice em coluna de baixa cardinalidade ajuda
menos que em colunas seletivas (FKs, por exemplo) — mantido mesmo assim
porque essa consulta roda com frequência nas views de BI e no dashboard
operacional.

## Como reproduzir

```bash
python -m scripts.runner --target analytics --group schema
python -m scripts.seed.load_data --target analytics --rows 30000
psql "$DB_ANALYTICS_URL" -c "EXPLAIN ANALYZE SELECT * FROM proposal_item WHERE fk_proposal = '<uuid>';"
python -m scripts.runner --target analytics --group indexes
# repetir o EXPLAIN ANALYZE acima para comparar
```
