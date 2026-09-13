include .env

.PHONY: migrate schema seed dataload indexes enums reset reset-mongo backup deps-windows

TARGET ?= local
ENVIRONMENT ?= local
ROWS ?= 1000

### So o ambiente "qa" usa sufixo -- local e prod usam o nome puro do
### banco (coredb/authdb), cada um no seu proprio host. Confirmado contra
### os secrets reais do Infisical (infra-platform/scripts/extract-env.ps1).
ifeq ($(ENVIRONMENT),qa)
	SUFIX = qa
else
	SUFIX =
endif

DB_NAME = $(TARGET)db$(SUFIX)
DATABASE_URI = postgresql://$(USER):$(PASSWORD)@$(HOST):$(PORT)/$(DB_NAME)
### reset precisa de uma conexao de manutencao -- nao da pra DROP DATABASE
### estando conectado nele mesmo.
MAINT_URI = postgresql://$(USER):$(PASSWORD)@$(HOST):$(PORT)/postgres

### mongo nao tem sufixo qa/prod no nome do banco -- o Infisical ja
### entrega DB_MONGO_URI/DB_MONGO_MESSENGER com o valor certo por
### ambiente (mesma convencao do api-messenger).
MONGO_URI = $(DB_MONGO_URI)/$(DB_MONGO_MESSENGER)

### Syntax Examples:
### - make {command} TARGET={database} ENVIRONMENT={environment}

PSQL = psql "$(DATABASE_URI)" -f

migrate:
	$(PSQL) db/$(TARGET)/migrations/V1__create_$(TARGET)_schema.sql

schema:
	$(PSQL) db/$(TARGET)/schema.sql

seed:
	$(PSQL) db/$(TARGET)/seed.sql

indexes:
	$(PSQL) db/$(TARGET)/indexes.sql

enums:
	$(PSQL) db/$(TARGET)/enums.sql

reset:
	psql "$(MAINT_URI)" -f db/reset.sql -v DB=$(DB_NAME)
	$(PSQL) db/$(TARGET)/schema.sql
	$(PSQL) db/$(TARGET)/enums.sql
	$(PSQL) db/$(TARGET)/seed.sql
	$(PSQL) db/$(TARGET)/indexes.sql

reset-mongo:
	mongosh "$(MONGO_URI)" db/messenger/reset.js

### dataload nao usa TARGET: auth_user/users compartilham UUID entre
### coredb e authdb, entao sempre popula os dois bancos juntos (ver
### scripts/dataload.py -- AUTH_STEPS roda contra authdb, CORE_STEPS
### contra coredb, na mesma execucao).
dataload:
	python -m scripts.dataload $(ROWS)

backup:
	pg_dump "$(DATABASE_URI)" > db/$(TARGET)/backup.sql

### instala via winget (nativo no Windows 10/11) as ferramentas de linha
### de comando usadas pelos targets acima: psql/pg_dump, python e mongosh.
deps-windows:
	winget install --id PostgreSQL.PostgreSQL.16 -e
	winget install --id Python.Python.3.12 -e
	winget install --id MongoDB.Shell -e

