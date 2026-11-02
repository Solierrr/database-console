<p align="center">
  <img src="../assets/readme/banners/postgresql.png" alt="PostgreSQL" width="100%">
</p>

# Arquitetura

O repositório contém scripts operacionais, seed e DDL de analytics. O schema de negócio pertence ao Flyway do `api-core`, e o de identidade ao Flyway do `api-auth`, diferentemente do checklist antigo.

```mermaid
flowchart LR
 O[Operador e Makefile] --> S[Scripts Python e sistema]
 S --> C[(PostgreSQL de negócio)]
 S --> A[(PostgreSQL de identidade)]
 S --> G[(PostgreSQL de indicadores)]
 M[mocks-warehouse] --> SE[Seed planejado]
 SE --> C
 SE --> A
 D[Databricks e databricks-sync] --> G
```

| Pasta | Papel |
|---|---|
| `seed/` | Plano, construção, imagens e carga determinística |
| `scripts/` | Papéis de acesso, carga volumétrica, backup e stack local |
| `db/roles/` | Contrato de privilégios por consumidor |
| `db/analytics/` | Schema de indicadores e autorização |
| `docker/` | Criação inicial dos bancos locais |

As conexões com o PostgreSQL usam as credenciais do ambiente, o backup usa `pg_dump` e a stack local inicia as APIs para que o Flyway de cada uma crie as suas estruturas. O mapa dos bancos está em [POSTGRES.md](../database/POSTGRES.md), e o fluxo analítico está em [ANALYTICS_SYNC.md](https://github.com/Solierrr/docs-warehouse/blob/main/docs/flows/ANALYTICS_SYNC.md).