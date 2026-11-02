<p align="center">
  <img src="../assets/readme/banners/postgresql.png" alt="PostgreSQL" width="100%">
</p>

# Execução local

O CI usa Python 3.14 e PostgreSQL 16, e localmente também são necessários o `make`, o Docker e os clientes `psql` e `pg_dump`, além do PowerShell para o backup. As dependências são instaladas com `make install`, e o `make vault` traz a configuração da pasta `/database`.

O procedimento comum de Python está em [PYTHON.md](https://github.com/Solierrr/docs-warehouse/blob/main/readme/running/PYTHON.md). A stack local exige os repositórios `api-core`, `api-auth` e `mocks-warehouse` nas posições esperadas por `scripts/dev-stack.sh`.

| Comando | Efeito |
|---|---|
| `make dev-up` | Inicia bancos e APIs e carrega seed |
| `make dev-db` | Inicia apenas bancos, com seed se o schema existir |
| `make dev-status` | Mostra a stack |
| `make dev-down` | Para a stack preservando o volume |
| `make seed-plan ARGS=--dry-run` | Confere plano sem gravar |
| `make roles-check` | Confere privilégios contra o contrato |
| `make test` | Unittest |
| `make lint` | Ruff nos scripts |
| `make build` | Compila scripts e seed |

Os testes com banco descartável usam a variável `SOLARIA_TEST_PG_DSN`, e o teste de seed precisa também de `SOLARIA_TEST_CORE_BASELINE`. Como a interface é de linha de comando, o repositório não tem contrato OpenAPI.