# Console dos principais Bancos de Dados

<p>

[![License](https://img.shields.io/github/license/Solierrr/web-app)](https://github.com/Solierrr/web-app/blob/main/LICENSE)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/Solierrr/web-app)](https://github.com/Solierrr/web-app/commits)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/Solierrr/web-app)](https://github.com/Solierrr/web-app/pulls)
[![GitHub Contributors](https://img.shields.io/github/contributors/Solierrr/web-app)](https://github.com/Solierrr/web-app/graphs/contributors)
[![Release](https://img.shields.io/github/v/release/Solierrr/web-app)](https://github.com/Solierrr/web-app/releases)

</p>

Repositório responsável por guardar, documentar e facilitar o uso de scripts, planejamentos e mudanças nos bancos de dados do projeto. É utilizado `Makefile` para facilitar a execução de scripts `SQL`. Todas as declarações de Triggers, Procedures, Functions, Indexes, Metadados (como Enums), entre outros; são guardados aqui nesse repositório de maneira organizada e granularizada. Além de toda organização para `SQL`, também há a presença de `python` para a execução de dataloads massivos com uso de Faker e dados pré-definidos.

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=postgresql,mongodb,python" height="64">
  </a>
</p>

## Segredos e backup PostgreSQL

Extraia as credenciais do ambiente desejado com `make extract-env SERVICE=database-console ENV=qa`. Sem argumentos, `make extract-env` pergunta o serviço e o ambiente. O arquivo `.env` é local e ignorado pelo Git.

`make backup` pergunta qual banco PostgreSQL salvar: `core`, `auth` ou ambos. Para executar sem menu, use `make backup TARGET=core`, `make backup TARGET=auth` ou `make backup TARGET=all`. O comando usa `DB_POSTGRES_*` do `.env` e grava arquivos SQL com data e hora em `backups/<ambiente>/`, diretório ignorado pelo Git. Para mudar o ambiente do backup, extraia primeiro o `.env` correspondente. O banco MongoDB de `messenger` não é incluído em `pg_dump`.

Os dumps podem conter dados sensíveis. Mantenha os arquivos fora do Git e compartilhe apenas por um canal aprovado pela equipe.

Para carregar dados no Databricks, use `make export-parquet TARGET=core` (ou `TARGET=auth` / `TARGET=all`). Sem `TARGET`, o comando pergunta qual banco exportar. Instale as dependências com `python -m pip install -r scripts/requirements.txt`. O exportador transmite as tabelas em lotes e cria uma pasta Parquet por tabela, com compressão Snappy, além de um `manifest.json`, em `exports/<ambiente>/<banco>/<data-hora-UTC>/`. Copie essa pasta para o armazenamento acessível ao Databricks; cada tabela pode ser lida separadamente, por exemplo `spark.read.parquet("<caminho>/public__company")`. Tipos UUID e enums viram texto; JSON e arrays viram texto JSON; números, datas, timestamps, booleanos e binários mantêm tipos Parquet compatíveis.

## Aprofunde-se no Projeto!

- [ARCHITECTURE.md](./ARCHITECTURE.md), estrutura de pastas e decisões de arquitetura do frontend.
- [RUNNING.md](./RUNNING.md), como rodar o projeto localmente.
- [DEPLOYMENT.md](https://github.com/Solierrr/.github/blob/main/.github/DEPLOYMENT.md), como o deploy funciona na organização.

## Contribuindo

- [CONTRIBUTING.md](https://github.com/Solierrr/.github/blob/main/.github/CONTRIBUTING.md), convenções de commit, branch e Pull Request.
- [CODE_OF_CONDUCT.md](https://github.com/Solierrr/.github/blob/main/.github/CODE_OF_CONDUCT.md), código de conduta do projeto.
- [SECURITY.md](https://github.com/Solierrr/.github/blob/main/.github/SECURITY.md), como reportar vulnerabilidades de segurança.
