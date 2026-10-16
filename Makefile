include .env
ifeq ($(OS),Windows_NT)
ORG_SCRIPTS_DIR ?= $(USERPROFILE)/.local/share/solierrr-infra-scripts
ORG_SCRIPTS_POWERSHELL ?= powershell
else
ORG_SCRIPTS_DIR ?= $(HOME)/.local/share/solierrr-infra-scripts
ORG_SCRIPTS_POWERSHELL ?= pwsh
endif
ORG_SCRIPTS_REPO ?= https://github.com/Solierrr/infra-scripts.git
EXTRACT_ENV := $(ORG_SCRIPTS_DIR)/scripts/extract-env.ps1
SERVICE ?=
ENV ?=
OUT ?= .env



.PHONY: dev-up dev-db dev-down dev-status dev-seed vault-config vault-auth extract-env tools-check env migrate schema seed seed-plan dataload indexes enums reset reset-mongo connect backup export-parquet deps-windows install





TARGET ?= local
ENVIRONMENT ?= local
ROWS ?= 1000

ifneq ($(filter qa QA "qa" "QA",$(ENVIRONMENT)),)
	SUFIX = qa
else
	SUFIX =
endif

unquote = $(subst ",,$(1))
DB_NAME = $(call unquote,$(TARGET))db$(SUFIX)
DATABASE_URI = postgresql://$(call unquote,$(USER)):$(call unquote,$(PASSWORD))@$(call unquote,$(HOST)):$(call unquote,$(PORT))/$(DB_NAME)
MAINT_URI = postgresql://$(call unquote,$(USER)):$(call unquote,$(PASSWORD))@$(call unquote,$(HOST)):$(call unquote,$(PORT))/postgres

MONGO_URI = $(call unquote,$(DB_MONGO_URI))/$(call unquote,$(DB_MONGO_MESSENGER))

### - make {command}
### - make {command} TARGET={database}
### - make {command} TARGET={database} ENVIRONMENT={environment}

PSQL = psql "$(DATABASE_URI)" -f

migrate:
	python scripts/migrate.py --target $(TARGET) $(if $(BASELINE),--baseline $(BASELINE),)

schema:
	$(PSQL) db/$(TARGET)/schema.sql

seed:
	$(PSQL) db/$(TARGET)/seed.sql

# Seed planejado (empresas, unidades, catalogo, tecnicos, propostas). Ex.: make seed-plan ARGS=--dry-run
seed-plan:
	python -m seed $(ARGS)

indexes:
	$(PSQL) db/$(TARGET)/indexes.sql

enums:
	$(PSQL) db/$(TARGET)/enums.sql

reset:
	psql "$(MAINT_URI)" -f db/reset.sql -v DB=$(DB_NAME)
	$(PSQL) db/$(TARGET)/enums.sql
	$(PSQL) db/$(TARGET)/schema.sql
	$(PSQL) db/$(TARGET)/seed.sql
	$(PSQL) db/$(TARGET)/indexes.sql

reset-mongo:
	mongosh "$(MONGO_URI)" db/messenger/reset.js

connect:
	psql "$(DATABASE_URI)"

dataload:
	python -m scripts.dataload $(ROWS)

backup:
	$(ORG_SCRIPTS_POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/backup-postgres.ps1 -Target "$(if $(filter command line,$(origin TARGET)),$(TARGET),)"

export-parquet:
	python scripts/export_parquet.py --target "$(if $(filter command line,$(origin TARGET)),$(TARGET),)"

install:
	winget install --id PostgreSQL.PostgreSQL.16 -e
	winget install --id Python.Python.3.12 -e
	winget install --id MongoDB.Shell -e

vault-config: ## Clone or update the shared infra-scripts toolkit
	$(ORG_SCRIPTS_POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/make-vault.ps1 -Action config -ScriptsDir "$(ORG_SCRIPTS_DIR)" -Repo "$(ORG_SCRIPTS_REPO)" -ExtractEnvPath "$(EXTRACT_ENV)"

vault-auth: vault-config ## Check that the Infisical CLI is installed and authenticated
	$(ORG_SCRIPTS_POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/make-vault.ps1 -Action auth

extract-env: vault-auth ## Generate a local environment file; prompts for missing service/environment
	$(ORG_SCRIPTS_POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/make-vault.ps1 -Action extract-env -ExtractEnvPath "$(EXTRACT_ENV)" -Service "$(SERVICE)" -Environment "$(ENV)" -OutputPath "$(OUT)"

tools-check: vault-config ## Alias for vault-config

env: extract-env ## Alias for extract-env

# Stack local de desenvolvimento (Postgres, Redis, api-auth, api-core + seed). Ver scripts/dev-stack.sh.
dev-up:
	sh scripts/dev-stack.sh up

# So o banco: Postgres e Redis, migrations e seed, e mostra a string de conexao do coredb.
dev-db:
	sh scripts/dev-stack.sh db

dev-down:
	sh scripts/dev-stack.sh down

dev-status:
	sh scripts/dev-stack.sh status

# Recarrega o seed; RESET=1 apaga antes o que o seed criou.
dev-seed:
	sh scripts/dev-stack.sh seed
