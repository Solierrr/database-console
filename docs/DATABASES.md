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

A composição usa PostgreSQL 16 e Redis 7. Os schemas reais devem ser consultados nos repositórios donos, não nos diagramas antigos do repositório de documentação.
