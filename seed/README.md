# Seed planejado

População inicial determinística para ambientes **locais ou de desenvolvimento**: empresas clientes com várias unidades coerentes com o ramo, fornecedores, catálogo de placas e de infraestrutura, técnicos, serviços, propostas e usuários com login. Serve ao desenvolvimento do web e ao `api-recommendation` (casos de borda propositais).

Não substitui `db/core/seed.sql` (mínimo) nem `scripts/dataload.py` (volume aleatório).

## Como rodar

Requisitos: Python com `psycopg2-binary`, `PyYAML` e `python-dotenv` (`scripts/requirements.txt`), o schema aplicado (`make migrate` ou `make schema`) nos dois bancos e o `mocks-warehouse` ao lado deste repositório.

```sh
# 1) ver o que será criado e o que falta de imagens, sem tocar no banco
python -m seed --dry-run

# 2) carregar (core + auth)
ENVIRONMENT=local CLOUDINARY_CLOUD_NAME=<cloud do Solaria> python -m seed

# apagar apenas o que este seed criou (IDs deterministicos)
ENVIRONMENT=local python -m seed --reset
```

Variáveis (mesma convenção do `dataload.py`): `HOST`, `PORT`, `USER`, `PASSWORD`, `SSLMODE` e `ENVIRONMENT`. Os bancos são `coredb` e `authdb`; use `SEED_CORE_DB` e `SEED_AUTH_DB` para outros nomes. O seed **recusa rodar** se `ENVIRONMENT` não estiver em `allowed_environments` do `plan.yaml` (`local` e `dev`), então nunca roda em QA ou produção.

Opções: `--today AAAA-MM-DD` (data de referência das assinaturas, ofertas e serviços), `--strict-images` (falha se faltar imagem), `--core-only` (não toca no banco de auth), `--manifest` e `--plan`.

É idempotente: uma segunda execução não duplica nada (`ON CONFLICT DO NOTHING` em IDs derivados do plano). Datas relativas (assinaturas, validade das ofertas) são calculadas na primeira carga; use `--reset` e carregue de novo para renová-las.

## Login de desenvolvimento

Todos os usuários criados usam a mesma senha, só válida localmente: `Seed-8fdPTytyex`. O e-mail de cada um é `<username>@seed.solaria.dev`. Para listar: `SELECT username FROM users` no `coredb`.

### Contas fixas por cargo

Além dos usuários com nomes sorteados, o seed cria contas fixas (e-mail `<usuario>@seed.solaria.dev`, mesma senha) em `dev_accounts` do `plan.yaml`:

| Usuário | Cargo | Empresa |
|---|---|---|
| `dev_dem_admin`, `dev_dem_manager`, `dev_dem_support` | ADMIN, MANAGER, SUPPORT | Rede Aurora Hoteis (demandante) |
| `dev_forn_admin`, `dev_forn_manager`, `dev_forn_sales` | ADMIN, MANAGER, SALES | SolMax Distribuidora (fornecedor) |
| `dev_tec_admin`, `dev_tec_manager`, `dev_tec_support`, `dev_tec_technician` | ADMIN, MANAGER, SUPPORT, TECHNICIAN | Instalacoes Raio de Sol (fornecedor, empresa técnica) |
| `dev_platform_admin` | Admin Solaria | sem empresa |

Permissões por cargo (`position_permissions` no `plan.yaml`): ADMIN passa por tudo e é o único que gerencia cargos e permissões; MANAGER opera ofertas, modelos, unidades, convites e equipes; SALES cuida de ofertas e modelos; SUPPORT e TECHNICIAN só leem. Endpoints fora do catálogo `permission` continuam só para ADMIN.

São criadas no fim do build, então não alteram nenhum dado sorteado antes delas. O `TECHNICIAN` só existe em empresa técnica.

## Projetos

Cada projeto (`technical_project`) sai com nome, descrição, situação (derivada dos serviços), local, participantes (`project_member`), atividades, histórico e fotos (`project_photo`, JPEG convertido do `mocks-warehouse` e gravado como bytes, que é como a API guarda). Detalhes e armadilhas em `projects/solaria/relatorios/2026-10-13-consumo-de-mocks.md`, seção 11. Para aplicar mudanças do seed em um banco já carregado use `RESET=1` (`make dev-seed RESET=1` ou `RESET=1 sh scripts/dev-stack.sh seed`), porque a carga não atualiza linhas existentes. Requer Pillow (`scripts/requirements.txt`).

## Imagens

Cada entidade recebe imagens do `manifest.json` do `mocks-warehouse`, escolhidas por categoria com estas regras:

- **Nunca repetem:** pfp de usuário, logo de empresa, banner de empresa, principal e banner de unidade, imagens de produto de infraestrutura.
- **Podem repetir:** banner de usuário, galeria de unidade, principal e galeria de placa solar.
- Unidades usam as imagens do ramo da empresa (`units/<segmento>/...`); banner de empresa vem do tema do perfil (`enterprises/banners/<tema>`).

As URLs seguem `https://res.cloudinary.com/<cloud>/image/upload/mocks/<id>.webp` e o `public_id` é `mocks/<id>`. O prefixo `mocks/` é protegido no `api-core` (apagar uma foto do seed nunca destrói o asset compartilhado). O upload dos arquivos para o Cloudinary é um passo à parte.

Se um pool não tiver imagens suficientes, a linha é criada sem aquela foto e o relatório (`--dry-run`) lista o que falta por categoria. Esse relatório é o orçamento de imagens a conseguir.

## O que o plano cria

Definido em `plan.yaml`: 15 empresas clientes e 64 unidades (uma rede de hotéis com 10), 6 fornecedores (um com assinatura vencida) e 5 empresas técnicas; 45 modelos de placa e 6 produtos de infraestrutura com 122 ofertas; 40 técnicos em 8 profissões; 150 serviços técnicos com avaliações; 30 propostas; 10 cidades em 5 regiões. Nomes e dados são fictícios.

Casos de borda para testar filtros: modelos em análise e reprovados, ofertas expiradas e pausadas, estoque zerado, assinatura vencida, empresas em análise e reprovadas, registros profissionais vencidos.

## Testes

`python -m unittest tests.test_seed` (plano e invariantes) e, com `SOLARIA_TEST_PG_DSN` apontando para um Postgres descartável, o teste de carga/idempotência/reset.


### Conta única para testar a interface

`teste@teste` / `Batata123` é uma conta exclusiva do seed local: profissional, administradora da plataforma e ADMIN nas empresas Rede Aurora Hoteis, SolMax Distribuidora e Raio de Sol. Possui participação de gestão nos projetos do seed. As contas por cargo permanecem disponíveis para testar permissões mais restritas. A conta é criada no fim do build sem alterar IDs ou dados das contas existentes. A carga incremental não exige reset.

## Compras de demonstração

O bloco `orders` do `plan.yaml` cria pedidos e carrinhos de exemplo para as telas de compra (pagamentos fictícios, nenhum valor real): quatro pedidos (pagos e um cancelado, alguns com itens de dois fornecedores) e dois carrinhos. Cada pedido grava o preço, o desconto e o nome do modelo no momento da compra, a taxa de 0,5% (`fee_percentage`) paga pelo comprador e um pagamento (`PIX`, `CREDIT_CARD`, `BOLETO` ou `TRANSFER`, sem lógica). O estoque da oferta (`availability`) é descontado só dos pedidos pagos.

Quem compra: o administrador de uma empresa demandante (`buyer: demandant`) ou um profissional registrado (`buyer: professional`). Usuário de empresa fornecedora não compra, a menos que seja profissional registrado e aprovado, e ninguém compra de uma empresa fornecedora a que pertence: o seed escolhe só ofertas de outros fornecedores. O sorteio dos pedidos usa um gerador próprio, então não desloca nenhum outro dado do seed.
