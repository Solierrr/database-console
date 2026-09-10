include .env

.PHONY: migrate schema seed dataload indexes enums reset backup

TARGET ?= local
ENVIRONMENT ?= local

ifeq ($(ENVIRONMENT),prod)
	SUFIX = db
else
	SUFIX = dbqa
endif

DATABASE_URI = postgresql://$(USER):$(PASSWORD)@$(HOST):$(PORT)/$(TARGET)$(SUFIX)

### Syntax Example: make {command} TARGET={database} ENVIRONMENT={}

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
	$(PSQL) db/$(TARGET)/reset.sql

dataload:
	

backup:
	pg_dump "$(DATABASE_URI)" > db/$(TARGET)/backup.sql

