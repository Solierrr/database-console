<p align="center">
  <img src="../assets/readme/banners/postgresql.png" alt="PostgreSQL" width="100%">
</p>

# Normalização do coredb

O `coredb` é normalizado até a terceira forma normal (3FN), com exceções conscientes e documentadas. O schema completo é do Flyway do `api-core` ([`V1__baseline.sql`](https://github.com/Solierrr/api-core/blob/main/src/main/resources/db/migration/V1__baseline.sql)) e tem 68 tabelas e 115 chaves estrangeiras. O diagrama de entidades está em [`database/POSTGRES.md`](https://github.com/Solierrr/api-core/blob/main/database/POSTGRES.md) do `api-core`.

## 1FN: valores atômicos e linhas identificáveis

- Toda tabela tem chave primária. A maioria usa uma coluna `id` do tipo `uuid`.
- Cada coluna guarda um único valor do domínio: preço, quantidade, estado, cidade e CEP são colunas separadas, e não um texto livre.
- Exceção: `user_account.connection_user_ids` (no `coredb`) e `auth_session.authentication_methods` (no `authdb`) são arrays. Foi uma troca consciente por simplicidade e leitura rápida. Se for preciso integridade referencial das conexões, o caminho é uma tabela de ligação `user_connection(user_id, connected_user_id)`.

## 2FN: sem dependência parcial da chave

As chaves primárias são simples (`id`), então não há dependência parcial. Nas tabelas de ligação N:N a chave é composta ou há uma restrição de unicidade sobre o par:

| Tabela | Relação N:N | Chave ou unicidade |
|---|---|---|
| `technician_specialty` | técnico e especialidade | `PRIMARY KEY (technician_id, specialty)` |
| `project_member` | projeto técnico e usuário | `UNIQUE (technical_project_id, user_id)` |
| `position_permission` | cargo (`job_position`) e permissão | `id` com as duas chaves estrangeiras |
| `technician_affiliation` | técnico e empresa | `id` com as duas chaves estrangeiras |
| `user_company` | usuário e empresa | `UNIQUE (user_id)`: cada usuário pertence a uma empresa |

## 3FN: sem dependência transitiva

Cada fato mora na tabela do seu dono, e as outras só guardam a chave estrangeira:

| Fato | Tabela dona | Quem referencia |
|---|---|---|
| Endereço (estado, cidade, rua, CEP) | `address` | `company`, `local_unit` |
| Nome e tipo da empresa, CNPJ | `company` | `supplier`, `requester` (por `company_id`) |
| Nome e logotipo da marca | `brand` | `model` (por `brand_id`) |
| Potência, eficiência, dimensões | `model` | `offer` (por `model_id`) |
| Preço e disponibilidade | `offer` | `proposal_item`, `order_item` |
| Nome e valor do plano | `company_plan` | `subscription` |
| Itens de uma negociação | `proposal_item` | ligada a `proposal` |
| Itens de uma compra | `order_item` | ligada a `purchase_order` |

Por exemplo, o estado de uma empresa não fica em `company`: ele depende do endereço, e o endereço depende da empresa só pela chave. Se ficasse em `company`, haveria uma dependência transitiva (`company` → `address` → estado).

## Desnormalizações conscientes

| Onde | O que se repete | Por quê | Como se mantém correto |
|---|---|---|---|
| `order_item.model_name`, `unit_price`, `offer_slug` | Dados da oferta no momento da compra | O pedido é um registro histórico: se a oferta mudar de preço, o pedido não pode mudar | Copiados da oferta na hora da compra; o pedido não relê a oferta depois |
| `purchase_order.subtotal_amount`, `fee_amount`, `total_amount` | Soma dos itens e taxa | Evita somar os itens em toda listagem | Calculados na criação do pedido e protegidos por restrições (`CHECK`) |
| `proposal.total_amount` | Soma dos itens negociados | Listagem rápida das propostas | A procedure [`regras.recalcular_total_proposta`](../db/modelagem/30_procedures.sql) recalcula a partir dos itens |
| Arrays de `user_account` e `auth_session` | Listas de valores | Ver 1FN | Atualizados pela aplicação |

## 4FN e 5FN

Não houve necessidade. Cada relação N:N fica em uma tabela de ligação própria, com um par de entidades, então não há fatos multivalorados independentes empilhados na mesma tabela (4FN) nem junções que só se reconstroem a partir de três ou mais tabelas (5FN).
