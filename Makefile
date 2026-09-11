include .env

.PHONY: migrate schema seed dataload indexes enums reset backup

TARGET ?= local
ENVIRONMENT ?= local
ROWS ?= 1000

ifeq ($(ENVIRONMENT),prod)
	SUFIX = db
else
	SUFIX = dbqa
endif

DATABASE_URI = postgresql://$(USER):$(PASSWORD)@$(HOST):$(PORT)/$(TARGET)$(SUFIX)

### Syntax Examples:
### - make {command} TARGET={database} ENVIRONMENT={environment}

PSQL = psql "$(DATABASE_URI)" -f

migrate:
	$(PSQL) migrations/V1__create_$(TARGET)_schema.sql

schema:
	$(PSQL) db/$(TARGET)/schema.sql

seed:
	$(PSQL) db/$(TARGET)/seed.sql

indexes:
	$(PSQL) db/$(TARGET)/indexes.sql

enums:
	$(PSQL) db/$(TARGET)/enums.sql

reset:
	$(PSQL) db/reset.sql -v DB=$(TARGET)
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

