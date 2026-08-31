# database-console

Ponto central para tudo relacionado aos bancos de dados do Solaria: scripts SQL
(schema, views analiticas, functions, procedures, triggers, indices,
governanca e monitoramento) e os scripts Python que os aplicam e carregam
dados de teste.

As migrations dos bancos operacionais (`api-core`, `api-auth`) continuam
vivendo nos respectivos repositorios Spring (Flyway). Este repo nao gerencia
o schema deles -- apenas roda scripts pontuais e hospeda o banco normalizado
novo do projeto interdisciplinar.

## Estrutura

```
db/
  schema/       DDL do banco normalizado (tabelas, PKs, FKs), por area de dominio
  governance/   catalogo de dados (metadados de tabelas/colunas/regras/acesso)
  monitoring/   log de acesso e view de DAU (usuarios ativos diarios)
  functions/    funcoes SQL de regra de negocio
  procedures/   procedures SQL de regra de negocio
  triggers/     triggers de auditoria (NEW/OLD/TG_OP/CURRENT_USER)
  views/        camada de BI (star schema) com CTEs e window functions
  indexes/      indices de otimizacao

scripts/
  db/           helper de conexao por banco-alvo (core, auth, analytics)
  seed/         geracao de massa de dados de teste (Faker)
  runner.py     aplica os .sql de uma pasta db/ contra um banco-alvo
```

## Uso

```bash
pip install -r requirements.txt
cp .env.example .env   # preencher com as credenciais reais

# aplica um grupo especifico contra o banco novo (analytics)
python -m scripts.runner --target analytics --group schema

# aplica tudo, na ordem correta de dependencia
python -m scripts.runner --target analytics --group all

# gera e insere massa de dados de teste
python -m scripts.seed.load_data --target analytics --rows 1000
```

`--target` aceita `core`, `auth` ou `analytics`, apontando para o banco
correspondente definido no `.env`.
