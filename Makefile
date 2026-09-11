include .env

.PHONY: migrate schema seed dataload indexes enums reset backup

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

### dataload nao usa TARGET: auth_user/users compartilham UUID entre
### coredb e authdb, entao sempre popula os dois bancos juntos (ver
### scripts/dataload.py -- AUTH_STEPS roda contra authdb, CORE_STEPS
### contra coredb, na mesma execucao).
dataload:
	python -m scripts.dataload $(ROWS)

backup:
	pg_dump "$(DATABASE_URI)" > db/$(TARGET)/backup.sql

