# Console dos principais Bancos de Dados

<p>

[![License](https://img.shields.io/github/license/Solierrr/web-app)](https://github.com/Solierrr/web-app/blob/main/LICENSE)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/Solierrr/web-app)](https://github.com/Solierrr/web-app/commits)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/Solierrr/web-app)](https://github.com/Solierrr/web-app/pulls)
[![GitHub Contributors](https://img.shields.io/github/contributors/Solierrr/web-app)](https://github.com/Solierrr/web-app/graphs/contributors)
[![Release](https://img.shields.io/github/v/release/Solierrr/web-app)](https://github.com/Solierrr/web-app/releases)

</p>

Repositório responsável por guardar, documentar e facilitar o uso dos scripts de apoio aos bancos de dados do projeto: o seed (planejado e volumétrico, com Faker e dados pré-definidos), os papéis de acesso direto, o backup e o `analyticsdb`. O DDL do `coredb` e do `authdb` não vive aqui: o Flyway do `api-core` e o do `api-auth` são os únicos donos. Usa `Makefile` para facilitar a execução dos scripts.

## Banco de analytics

Use `make create TARGET=analytics ENVIRONMENT=prod` para criar o banco PostgreSQL `analyticsdb` sem apagar um banco existente. Depois, `make schema TARGET=analytics ENVIRONMENT=prod` cria o schema de destino e o controle de acesso. Com `ENVIRONMENT=qa`, o nome segue a convenção do repositório e passa a ser `analyticsdbqa`. O `databricks-sync` exporta para esse banco as views Gold já calculadas pelo `databricks-stocker`, conforme [contrato de destino analytics](db/analytics/README.md). Para abrir uma sessão, use `make connect TARGET=analytics ENVIRONMENT=prod`. Nenhum desses comandos é executado automaticamente.

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=postgresql,mongodb,python" height="64">
  </a>
</p>

## Consumir o coredb localmente

`make dev-up` sobe o Postgres e o Redis em Docker e o `api-auth` e o `api-core`, cujo Flyway cria o `coredb` e o `authdb`; depois carrega o seed planejado. `make dev-db` sobe só o Postgres e o Redis e carrega o seed se o schema já existir (caso contrário, avisa para rodar `make dev-up` primeiro). A string de conexão é `postgresql://solaria:solaria@localhost:55432/coredb` (porta ajustável por `SOLARIA_PG_PORT`). `make dev-status` mostra o que está de pé e `make dev-down` para tudo e mantém os dados no volume.

Os containers se chamam `local-database-console-postgres` e `local-database-console-redis`. Quem já tinha os containers antigos (`solaria-postgres` e `solaria-redis`, parados) pode removê-los com `docker rm solaria-postgres solaria-redis`: os dados ficam no volume `solaria-pgdata`, que o compose continua usando.

## Segredos e backup PostgreSQL

Para testar o que depende de um Postgres, defina `SOLARIA_TEST_PG_DSN` apontando para um Postgres descartável e execute `python -m unittest discover -s tests -v`. Os testes de papéis criam objetos próprios e os removem no fim. O teste de carga do seed também exige `SOLARIA_TEST_CORE_BASELINE`, a pasta `db/migration` do `api-core` (V1 a V3).

Extraia as credenciais do ambiente desejado com `make vault ENV=qa` (`local`, `qa` ou `prod`; o padrão é `local`). Ele grava o `.env` a partir do Infisical (pasta `/database`) e exige o Infisical CLI com `infisical login`. O arquivo `.env` é local e ignorado pelo Git. `make help` lista os demais comandos.

`make backup` pergunta qual banco PostgreSQL salvar: `core`, `auth` ou ambos. Para executar sem menu, use `make backup TARGET=core`, `make backup TARGET=auth` ou `make backup TARGET=all`. O comando usa `DB_POSTGRES_*` do `.env` e grava arquivos SQL com data e hora em `backups/<ambiente>/`, diretório ignorado pelo Git. Para mudar o ambiente do backup, extraia primeiro o `.env` correspondente. O banco MongoDB de `messenger` não é incluído em `pg_dump`.

Os dumps podem conter dados sensíveis. Mantenha os arquivos fora do Git e compartilhe apenas por um canal aprovado pela equipe.

## Papéis de acesso direto por consumidor

Quem lê o `coredb` ou o `authdb` direto (fora as APIs) usa um papel por consumidor, com o menor privilégio possível, definido em [`db/roles/contracts.json`](db/roles/contracts.json) e aplicado por [`scripts/roles.py`](scripts/roles.py):

- `ro_bootstrap` (`database-bootstrap`): lê 23 views do schema `export` do `coredb`, com grant por coluna em `person` e `user_account`.
- `ro_databricks` (`databricks-sync`): lê todas as views do schema `export` do `coredb` e do `authdb`.
- `rpa_writer` (`database-rpa`): exceção documentada ao dono único. `SELECT`, `INSERT` e `UPDATE` nas tabelas de `public` que o RPA usa, só em QA.

Os papéis de leitura não recebem nada em `public`. O schema `export` e suas views vêm do Flyway do `api-core` e do `api-auth`. `ro_recommendation` e `ro_mcp` não existem mais: `api-recommendation` e `mcp-database` usam a API do `api-core`.

```bash
make roles-apply                 # cria os papéis (sem login) e concede só o que o contrato libera
make roles-check                 # confere os bancos com o contrato; sai com 1 se divergir
make roles-apply ENVIRONMENT=qa  # inclui o rpa_writer, que só existe em QA
python scripts/roles.py login databricks-sync svc_databricks_core SENHA_DATABRICKS --database core
                                 # cria o login do consumidor; a senha vem da variável de ambiente, nunca de arquivo
```

Cada consumidor tem login próprio (o `databricks-sync` usa um por banco). Os papéis não herdam objetos novos: depois de mudar as views do `export`, atualize o contrato e rode `make roles-apply`. Em QA e produção quem cria os logins e guarda as senhas no Infisical é o dono; o script nunca imprime nem grava senha.

## De quem é o schema

- **`coredb`:** o dono é o Flyway do `api-core` (`V1__baseline.sql`, mais o schema `export`). Este repositório não tem DDL do `coredb`.
- **`authdb`:** o dono é o Flyway do `api-auth`. Não há espelho aqui.
- **`analyticsdb`:** o schema `gold` é criado por `db/analytics/schema.sql` (`make schema TARGET=analytics`).

Os bancos se chamam `coredb`/`coredbqa`, `authdb`/`authdbqa` e `analyticsdb`/`analyticsdbqa`.

## Aprofunde-se no Projeto!

- [ARCHITECTURE.md](./ARCHITECTURE.md), estrutura de pastas e decisões de arquitetura do frontend.
- [RUNNING.md](./RUNNING.md), como rodar o projeto localmente.
- [DEPLOYMENT.md](https://github.com/Solierrr/.github/blob/main/.github/DEPLOYMENT.md), como o deploy funciona na organização.

## Contribuindo

- [CONTRIBUTING.md](https://github.com/Solierrr/.github/blob/main/.github/CONTRIBUTING.md), convenções de commit, branch e Pull Request.
- [CODE_OF_CONDUCT.md](https://github.com/Solierrr/.github/blob/main/.github/CODE_OF_CONDUCT.md), código de conduta do projeto.
- [SECURITY.md](https://github.com/Solierrr/.github/blob/main/.github/SECURITY.md), como reportar vulnerabilidades de segurança.
