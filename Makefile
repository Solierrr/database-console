include .env

.PHONY: migrate schema seed dataload indexes enums reset reset-mongo connect backup deps-windows

TARGET ?= local
ENVIRONMENT ?= local
ROWS ?= 1000

ifeq ($(ENVIRONMENT),qa)
	SUFIX = qa
else
	SUFIX =
endif

DB_NAME = $(TARGET)db$(SUFIX)
DATABASE_URI = postgresql://$(USER):$(PASSWORD)@$(HOST):$(PORT)/$(DB_NAME)
MAINT_URI = postgresql://$(USER):$(PASSWORD)@$(HOST):$(PORT)/postgres

MONGO_URI = $(DB_MONGO_URI)/$(DB_MONGO_MESSENGER)

### - make {command}
### - make {command} TARGET={database}
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

connect:
	psql "$(DATABASE_URI)"

dataload:
	python -m scripts.dataload $(ROWS)

backup:
	pg_dump "$(DATABASE_URI)" > db/$(TARGET)/backup.sql

install:
	winget install --id PostgreSQL.PostgreSQL.16 -e
	winget install --id Python.Python.3.12 -e
	winget install --id MongoDB.Shell -e
