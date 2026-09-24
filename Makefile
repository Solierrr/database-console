include .env

ORG_SCRIPTS_DIR ?= $(HOME)/.local/share/solierrr-infra-scripts
ORG_SCRIPTS_REPO ?= https://github.com/Solierrr/infra-scripts.git
ORG_SCRIPTS_POWERSHELL ?= powershell
EXTRACT_ENV := $(ORG_SCRIPTS_DIR)/scripts/extract-env.ps1
SERVICE := database-console
ENV ?= local
OUT ?= .env

.PHONY: vault-config vault-auth extract-env tools-check env migrate schema seed dataload indexes enums reset reset-mongo connect backup deps-windows

vault-config:
	@if [ -d "$(ORG_SCRIPTS_DIR)/.git" ]; then \
		echo "infra-scripts found at $(ORG_SCRIPTS_DIR), updating..."; \
		git -C "$(ORG_SCRIPTS_DIR)" pull --ff-only || { echo "error: 'git pull --ff-only' failed in $(ORG_SCRIPTS_DIR). Resolve manually, then run 'make vault-config' again."; exit 1; }; \
	elif [ -e "$(ORG_SCRIPTS_DIR)" ]; then \
		echo "error: $(ORG_SCRIPTS_DIR) exists but is not a git clone. Remove or rename it, then run 'make vault-config' again."; exit 1; \
	else \
		echo "infra-scripts not found, cloning into $(ORG_SCRIPTS_DIR)..."; \
		git clone "$(ORG_SCRIPTS_REPO)" "$(ORG_SCRIPTS_DIR)" || { echo "error: failed to clone $(ORG_SCRIPTS_REPO). Check your network/access, then run 'make vault-config' again."; exit 1; }; \
	fi
	@test -f "$(EXTRACT_ENV)" || { echo "error: infra-scripts was cloned/updated but $(EXTRACT_ENV) is missing. Check if the script was renamed or moved upstream."; exit 1; }
	@echo "OK: infra-scripts ready at $(ORG_SCRIPTS_DIR)"

vault-auth: vault-config
	@command -v infisical >/dev/null 2>&1 || { echo "error: Infisical CLI not installed. Install it (https://infisical.com/docs/cli/overview), then run 'make vault-auth' again."; exit 1; }
	@infisical user get token --silent >/dev/null 2>&1 || { \
		echo "error: no active Infisical session."; \
		echo "Run: infisical login"; \
		echo "Then run 'make extract-env' again."; \
		exit 1; \
	}
	@echo "OK: Infisical authenticated."

extract-env: vault-auth
	@test -n "$(SERVICE)" || { echo "error: SERVICE not set. Example: make extract-env SERVICE=database-console"; exit 1; }
	@case "$(ENV)" in local|qa|prod) : ;; *) echo "error: invalid ENV '$(ENV)'. Use local, qa or prod (example: make extract-env ENV=qa)"; exit 1;; esac
	$(ORG_SCRIPTS_POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File "$(EXTRACT_ENV)" -Service "$(SERVICE)" -Environment "$(ENV)" -OutputPath "$(OUT)"

tools-check: vault-config
env: extract-env

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
	pg_dump "$(DATABASE_URI)" > db/$(TARGET)/backup.sql

install:
	winget install --id PostgreSQL.PostgreSQL.16 -e
	winget install --id Python.Python.3.12 -e
	winget install --id MongoDB.Shell -e
