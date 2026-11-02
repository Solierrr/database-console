<p align="center">
  <img src="../assets/readme/banners/postgresql.png" alt="PostgreSQL" width="100%">
</p>

# Mapa dos bancos

O mapa distingue a posse do schema da operação dos utilitários.

| Dados | Dono | Papel deste repositório |
|---|---|---|
| Negócio em PostgreSQL | `api-core` | Seed, backup e permissões diretas |
| Identidade em PostgreSQL | `api-auth` | Seed, backup e permissões diretas |
| Indicadores em PostgreSQL | Configuração local e exportador `databricks-sync` | Cria banco, schema e controle de acesso |
| Conversas em MongoDB | `api-messenger` | Script explícito de reset, fora do backup PostgreSQL |
| Recomendações em Neo4j | `database-bootstrap` e consumidor de feeds | Não hospeda o schema do grafo |
| Redis local | Docker Compose | Apoio à stack de desenvolvimento |

## Camada de modelagem

Por cima do schema do Flyway, o repositório mantém os objetos de modelagem de dados em `db/modelagem/`: o Data Mart em esquema estrela (`bi`), as funções e procedures de regras (`regras`), a auditoria por trigger (`audit`), o catálogo de dados (`governance`) e o monitoramento de DAU (`monitoring`). Esses objetos não alteram tabelas do Flyway: só acrescentam schemas, views, funções, triggers e índices. Por isso o Flyway continua sendo o único dono das tabelas, e os scripts são idempotentes (`make modelagem-apply`). Detalhes em [Data Mart](DATAMART.md), [normalização](NORMALIZACAO.md) e [otimização](OTIMIZACAO.md).

A composição usa PostgreSQL 16 e Redis 7. Os schemas reais devem ser consultados nos repositórios donos, não nos diagramas antigos do repositório de documentação.
