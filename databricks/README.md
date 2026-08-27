# databricks

Cron job que sincroniza dados de um banco Postgres para tabelas Delta no
Databricks (Unity Catalog), via full refresh periodico.

Esta pasta e exclusiva do cron job de sincronizacao com o Databricks. Scripts
de schema/dataload especificos de cada banco de origem vivem em outras pastas
do repositorio.

## Arquivos

- `sync_aiven_to_databricks.py` - le todas as tabelas do schema `public` da
  origem Postgres configurada e recria como tabelas Delta no catalogo/schema
  do Databricks definidos por env var.
- `requirements.txt` - dependencias Python do cron job.
- `dataload_test_data.py` - popula dados de teste no banco de origem (uso
  local, nao faz parte do deploy).

## Variaveis de ambiente

| Variavel | Descricao |
| --- | --- |
| `DB_CORE_HOST` | Host do Postgres de origem |
| `DB_CORE_PORT` | Porta do Postgres de origem |
| `DB_CORE_USER` | Usuario do Postgres de origem |
| `DB_CORE_PASS` | Senha do Postgres de origem |
| `DB_CORE_NAME` | Nome do banco de origem |
| `DATABRICKS_HOST` | Host do workspace Databricks (ex: `https://dbc-xxxx.cloud.databricks.com`) |
| `DATABRICKS_HTTP_PATH` | HTTP path do SQL Warehouse (ex: `/sql/1.0/warehouses/<id>`) |
| `DATABRICKS_TOKEN` | Personal Access Token do Databricks |
| `DATABRICKS_CATALOG` | Catalogo de destino no Unity Catalog (ex: `workspace`) |
| `DATABRICKS_SCHEMA` | Schema de destino (ex: `bronze_aiven`) |

Localmente, essas variaveis vem do `.env` na raiz de `database-console`
(veja `.env.example`). Em producao (Render), sao configuradas direto no
dashboard do servico — nunca commitadas.

## Deploy no Render

O arquivo `render.yaml` na raiz do repositorio define este cron job como um
Render Blueprint (`type: cron`, `rootDir: databricks`, schedule a cada 4h).
O `render.yaml` precisa ficar na raiz do repositorio porque e ali que o
Render Blueprint o procura — mesmo que a implementacao em si fique isolada
nesta pasta.

Passos:

1. Subir este repositorio (branch com o `render.yaml`) numa conta Render.
2. Criar um Blueprint apontando pro repositorio — o Render detecta o
   `render.yaml` automaticamente.
3. Preencher as env vars marcadas com `sync: false` no dashboard do servico
   criado (nao ficam no `render.yaml` por serem sensiveis).
4. O cron roda automaticamente no schedule `0 */4 * * *` (a cada 4 horas).
