<p align="center">
  <img src="./assets/readme/banners/postgresql.png" alt="PostgreSQL" width="100%">
</p>

<p align="center">
  <img src="./assets/readme/stacks/python.png" width="100" hspace="8" alt="Python" title="Python">
  <img src="./assets/readme/stacks/redis.png" width="100" hspace="8" alt="Redis" title="Redis">
</p>

# Operações de dados

[![License](https://img.shields.io/github/license/Solierrr/database-console)](https://github.com/Solierrr/database-console/blob/main/LICENSE)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/Solierrr/database-console)](https://github.com/Solierrr/database-console/commits)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/Solierrr/database-console)](https://github.com/Solierrr/database-console/pulls)
[![Release](https://img.shields.io/github/v/release/Solierrr/database-console)](https://github.com/Solierrr/database-console/releases)

Este repositório reúne as operações de apoio aos dados da plataforma. A equipe pode preparar um ambiente local, carregar dados de desenvolvimento, conferir permissões e produzir cópias de segurança. Os dados de identidade e de negócio continuam sob responsabilidade dos serviços que os mantêm, enquanto o destino de indicadores possui uma configuração própria aqui.

Os utilitários usam Python, clientes PostgreSQL e scripts de sistema. Uma composição Docker fornece PostgreSQL e Redis no desenvolvimento. As credenciais são obtidas pelo Infisical. O destino de indicadores recebe resultados calculados no Databricks, com acesso por login e escopo, e não serve de origem para calcular esses indicadores.

## Aprofunde-se no Projeto!

- [OVERVIEW.md](./docs/OVERVIEW.md), finalidade e regras de produto.
- [ARCHITECTURE.md](./docs/ARCHITECTURE.md), componentes, dados e integrações.
- [RUNNING.md](./docs/RUNNING.md), preparação e execução local.
- [DEPLOY.md](./docs/DEPLOY.md), ambientes e publicação.
- [STATUS.md](./docs/STATUS.md), limites observados.
- [DATABASES.md](./docs/DATABASES.md), detalhes do fluxo ou modelo de dados.
- [SECRETS_AND_BACKUP.md](./docs/SECRETS_AND_BACKUP.md), detalhes do fluxo ou modelo de dados.
- [Dados](./database/), modelos e responsabilidades de persistência.
- [Fluxos](./flows/), etapas e casos de erro do repositório.
- [PENDENCIAS.md](./PENDENCIAS.md), questões para revisão.

## Contribuindo

- [CONTRIBUTING.md](https://github.com/Solierrr/.github/blob/main/.github/CONTRIBUTING.md), convenções de contribuição.
- [CODE_OF_CONDUCT.md](https://github.com/Solierrr/.github/blob/main/CODE_OF_CONDUCT.md), código de conduta.
- [SECURITY.md](https://github.com/Solierrr/.github/blob/main/SECURITY.md), relato de vulnerabilidades.
