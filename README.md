# Console dos principais Bancos de Dados

<p>

[![License](https://img.shields.io/github/license/Solierrr/web-app)](https://github.com/Solierrr/web-app/blob/main/LICENSE)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/Solierrr/web-app)](https://github.com/Solierrr/web-app/commits)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/Solierrr/web-app)](https://github.com/Solierrr/web-app/pulls)
[![GitHub Contributors](https://img.shields.io/github/contributors/Solierrr/web-app)](https://github.com/Solierrr/web-app/graphs/contributors)
[![Release](https://img.shields.io/github/v/release/Solierrr/web-app)](https://github.com/Solierrr/web-app/releases)

</p>

Repositório responsável por guardar, documentar e facilitar o uso de scripts, planejamentos e mudanças nos bancos de dados do projeto. É utilizado `Makefile` para facilitar a execução de scripts `SQL`. Todas as declarações de Triggers, Procedures, Functions, Indexes, Metadados (como Enums), entre outros; são guardados aqui nesse repositório de maneira organizada e granularizada. Além de toda organização para `SQL`, também há a presença de `python` para a execução de dataloads massivos com uso de Faker e dados pré-definidos.

<p>
  <a href="https://github.com/syvixor/skills-icons">
    <img src="https://skills.syvixor.com/api/icons?i=postgresql,mongodb,python" height="64">
  </a>
</p>

## Consumir o coredb localmente

`make dev-db` sobe só o Postgres e o Redis em Docker, aplica as migrações de `core` e `auth` (inclusive o carrinho e os pedidos, V27 e V28), carrega o seed planejado e imprime como conectar: `postgresql://solaria:solaria@localhost:55432/coredb` (porta ajustável por `SOLARIA_PG_PORT`). Serve para apontar uma API ou um cliente SQL para o banco sem subir `api-auth` e `api-core`. `make dev-up` faz o mesmo e ainda sobe as duas APIs; `make dev-status` mostra o que está de pé; `make dev-down` para tudo e mantém os dados no volume.

Os containers se chamam `local-database-console-postgres` e `local-database-console-redis`. Quem já tinha os containers antigos (`solaria-postgres` e `solaria-redis`, parados) pode removê-los com `docker rm solaria-postgres solaria-redis`: os dados ficam no volume `solaria-pgdata`, que o compose continua usando.

## Carrinho e pedidos

As migrações `V27__marketplace_orders.sql` e `V28__purchase_permissions.sql` criam as tabelas `cart`, `cart_item`, `purchase_order`, `order_item` e `order_payment` e as permissões de compra no catálogo (`permission`). O pedido guarda uma cópia do preço, do desconto e do nome do modelo; o pagamento é fictício. Duas regras valem também no banco, por gatilho: usuário de empresa fornecedora só compra se for profissional registrado e aprovado, e ninguém compra de uma empresa fornecedora a que pertence. A spec está no VersioSpec (`marketplace/pagamentos`). Os testes são `tests/test_marketplace_migration.py`.

## Segredos e backup PostgreSQL

### Migrations do core

`make migrate TARGET=core` executa todas as migrations em ordem usando `scripts/migrate.py`, com as variáveis `DB_POSTGRES_*` já usadas pelo exportador. Cada migration e seu registro em `solaria_schema_history` são gravados na mesma transação. O runner confere checksums e serializa execuções concorrentes. Não alterar migrations já aplicadas.

Para um banco existente sem histórico, primeiro conferir sua estrutura contra as versões e executar o diagnóstico `db/core/diagnostics.sql` depois da V12. Somente após confirmar o baseline, usar `make migrate TARGET=core BASELINE=11` se ele já corresponder às V1–V11. Baseline registra versões como já presentes; não executa nem verifica automaticamente seus SQLs. Bancos divergentes precisam ser reconciliados antes, sem descartar dados.

Instalações novas devem preferir o runner desde a V1. `schema.sql` permanece como alternativa de instalação vazia, incluindo as estruturas novas; não executar sobre um banco já instalado nem executar V1 novamente após esse caminho. Os scripts antigos `api-core/src/main/resources/db/deeplink.sql` e `api-core/database/schema-user-connections.sql` foram substituídos por avisos: a fonte executável agora fica aqui. Seeds são apenas para desenvolvimento.

As migrations V12–V18 cobrem validação/documentos privados, integridade de estoque/ofertas, fila de tradução, estados/histórico de ofertas, equipes, índices e permissões. Duplicidades e valores inválidos interrompem a migration; não há saneamento automático. Novas permissões entram no catálogo e precisam ser atribuídas aos cargos apropriados.

Para testar em um PostgreSQL isolado, definir `SOLARIA_TEST_PG_DSN` e executar `python -m unittest discover -s tests -v`. Os testes usam schemas temporários próprios e removem somente esses schemas no encerramento.

Extraia as credenciais do ambiente desejado com `make vault ENV=qa` (`local`, `qa` ou `prod`; o padrão é `local`). Ele grava o `.env` a partir do Infisical (pasta `/database`) e exige o Infisical CLI com `infisical login`. O arquivo `.env` é local e ignorado pelo Git. `make help` lista os demais comandos.

`make backup` pergunta qual banco PostgreSQL salvar: `core`, `auth` ou ambos. Para executar sem menu, use `make backup TARGET=core`, `make backup TARGET=auth` ou `make backup TARGET=all`. O comando usa `DB_POSTGRES_*` do `.env` e grava arquivos SQL com data e hora em `backups/<ambiente>/`, diretório ignorado pelo Git. Para mudar o ambiente do backup, extraia primeiro o `.env` correspondente. O banco MongoDB de `messenger` não é incluído em `pg_dump`.

Os dumps podem conter dados sensíveis. Mantenha os arquivos fora do Git e compartilhe apenas por um canal aprovado pela equipe.

## Acesso de leitura ao coredb por consumidor

Quem lê o `coredb` direto (fora o `api-core`) usa um usuário somente leitura, um por consumidor, com o menor privilégio possível. O contrato de cada um (tabelas e colunas que ele lê) está em [`db/roles/contracts.json`](db/roles/contracts.json) e é aplicado por [`scripts/roles.py`](scripts/roles.py): `api-recommendation`, `database-bootstrap`, `mcp-database` e `databricks-sync` (este último é uma proposta que depende de confirmar o que o pipeline precisa). O `database-rpa` não tem papel: a decisão é aposentá-lo (ver a spec de acesso ao `coredb` no VersioSpec).

```bash
make roles-apply                 # cria os papéis solaria_ro_* (sem login) e concede só SELECT, conforme o contrato
make roles-check                 # confere o banco com o contrato; sai com 1 se divergir (permissão a mais ou a menos)
python scripts/roles.py login api-recommendation svc_recommendation SENHA_RECOMENDACAO
                                 # cria o login do consumidor; a senha vem da variável de ambiente, nunca de arquivo
```

Os papéis não herdam tabelas novas: depois de uma migration que cria tabela ou coluna que um consumidor passa a ler, atualize o contrato e rode `make roles-apply` (o `roles-check` acusa a diferença). Em QA e produção quem cria os logins e guarda as senhas no Infisical é o dono; o script nunca imprime nem grava senha.

## De quem é o schema

- **`coredb`:** a fonte única é este repositório (`db/core/schema.sql` para instalação vazia e `db/core/migrations` para evoluir). O `api-core` não tem migrações próprias e roda com `ddl-auto=validate`, só conferindo o banco contra as entidades. Não existem outras cópias do DDL: o `schema-user-connections.sql` do `api-core` e o `schema_negocio.sql` do `mcp-database` foram removidos.
- **`authdb`:** o autor das migrations é o `api-auth` (`src/main/resources/db/migration`, Flyway). Os arquivos de `db/auth/migrations` daqui são um **espelho** dos dele: nos ambientes quem os executa é `scripts/migrate.py --target auth`, com o Flyway do `api-auth` desligado (`SPRING_FLYWAY_ENABLED=false`); ligar os dois no mesmo banco faria o Flyway tentar recriar o que o `migrate.py` já criou. Uma migration nova nasce no `api-auth` e é copiada para cá; `make auth-mirror-check` (`API_AUTH_DIR` aponta para o clone do `api-auth`, padrão `../api-auth`) acusa arquivo que falta, que sobra ou que difere, ignorando só os comentários do começo.

Para carregar dados no Databricks, use `make export-parquet TARGET=core` (ou `TARGET=auth` / `TARGET=all`). Sem `TARGET`, o comando pergunta qual banco exportar. Instale as dependências com `python -m pip install -r scripts/requirements.txt`. O exportador transmite as tabelas em lotes e cria uma pasta Parquet por tabela, com compressão Snappy, além de um `manifest.json`, em `exports/<ambiente>/<banco>/<data-hora-UTC>/`. Copie essa pasta para o armazenamento acessível ao Databricks; cada tabela pode ser lida separadamente, por exemplo `spark.read.parquet("<caminho>/public__company")`. Tipos UUID e enums viram texto; JSON e arrays viram texto JSON; números, datas, timestamps, booleanos e binários mantêm tipos Parquet compatíveis.

## Aprofunde-se no Projeto!

- [ARCHITECTURE.md](./ARCHITECTURE.md), estrutura de pastas e decisões de arquitetura do frontend.
- [RUNNING.md](./RUNNING.md), como rodar o projeto localmente.
- [DEPLOYMENT.md](https://github.com/Solierrr/.github/blob/main/.github/DEPLOYMENT.md), como o deploy funciona na organização.

## Contribuindo

- [CONTRIBUTING.md](https://github.com/Solierrr/.github/blob/main/.github/CONTRIBUTING.md), convenções de commit, branch e Pull Request.
- [CODE_OF_CONDUCT.md](https://github.com/Solierrr/.github/blob/main/.github/CODE_OF_CONDUCT.md), código de conduta do projeto.
- [SECURITY.md](https://github.com/Solierrr/.github/blob/main/.github/SECURITY.md), como reportar vulnerabilidades de segurança.


### Projetos privados (V24)

V24 inclui propriedade empresarial/profissional, participação, convites, agenda, histórico e fotos privadas. Preserva empresa/local/executores dos projetos antigos e disponibiliza seus serviços na agenda, mantendo término desconhecido vazio. Status de projetos/serviços e tipo de afiliação ficam em varchar com constraints, alinhados ao JPA. Afiliação independente pode ter empresa nula; nenhuma relação de emprego é criada.

Banco existente: aplicar V24 após V23. Banco novo: schema consolidado já inclui V24; baseline deve ser 24 antes de usar o executor. Testes específicos: `python -m unittest discover -s tests -p test_projects_migration.py -v` com SOLARIA_TEST_PG_DSN apontando para um PostgreSQL descartável.
