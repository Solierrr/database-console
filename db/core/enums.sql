-- =============================================================================
-- db/core/enums.sql
--
-- Extensoes e tipos enumerados do banco do api-core (com.solaria.persistence:
-- empresas, propostas, catalogo de fornecedores, tecnicos e execucao de
-- servico). Extraido das enums Java em
-- api-core/src/main/java/com/solaria/persistence/domain/enums/.
--
-- IMPORTANTE: api-core roda com spring.jpa.hibernate.ddl-auto=validate mas
-- NAO possui nenhuma migration Flyway nem schema.sql proprio -- o schema real
-- hoje existe apenas como entidades JPA. Este arquivo (e db/core/schema.sql)
-- e a fonte de verdade versionada desse schema ate que o api-core adote
-- Flyway. Qualquer mudanca em uma @Entity ou enum do api-core deve ser
-- refletida aqui manualmente.
--
-- Rode antes de schema.sql.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_uuid()

-- Situacao de faturamento de uma cobranca (charge.status).
CREATE TYPE billing_status AS ENUM (
    'PENDING',
    'PAID',
    'CANCELED',
    'REFUNDED'
);

-- Situacao cadastral de uma empresa (company.status).
CREATE TYPE company_status AS ENUM (
    'UNDER_ANALYSIS',
    'APPROVED',
    'REJECTED'
);

-- Dia da semana de um turno de tecnico (shift.day_week).
CREATE TYPE day_week AS ENUM (
    'MONDAY',
    'TUESDAY',
    'WEDNESDAY',
    'THURSDAY',
    'FRIDAY',
    'SATURDAY',
    'SUNDAY'
);

-- Tipo do local de instalacao de uma unidade (local_unit.location_type).
CREATE TYPE location_type AS ENUM (
    'BUILDING',
    'HOUSE',
    'COMPLEX'
);

-- Situacao de homologacao de um modelo de painel (model.status).
CREATE TYPE model_status AS ENUM (
    'APPROVED',
    'REJECTED',
    'UNDER_ANALYSIS'
);

-- Metodo de pagamento de uma cobranca (charge.payment_method).
CREATE TYPE payment_method AS ENUM (
    'PIX',
    'BOLETO',
    'CREDIT_CARD',
    'TRANSFER'
);

-- Periodicidade de cobranca de um plano (company_plans.cycle).
CREATE TYPE plan_cycle AS ENUM (
    'MONTHLY',
    'QUARTERLY',
    'YEARLY'
);

-- Fluxo de negociacao de uma proposta (proposal.status).
CREATE TYPE proposal_status AS ENUM (
    'AWAITING_SUPPLIER',
    'AWAITING_REQUESTER',
    'ACCEPTED',
    'REJECTED',
    'CANCELED'
);

-- Andamento de um servico tecnico ou projeto (technical_service.status,
-- technical_project.status).
CREATE TYPE service_status AS ENUM (
    'OPEN',
    'IN_PROGRESS',
    'COMPLETED',
    'CANCELED'
);

-- Situacao de adimplencia de uma assinatura (subscription.status).
CREATE TYPE subscription_status AS ENUM (
    'PAID',
    'IN_DEBT',
    'SUSPENDED'
);

-- Situacao cadastral de um fornecedor (supplier.status).
CREATE TYPE supplier_status AS ENUM (
    'ACTIVE',
    'SUSPENDED',
    'DEACTIVATED'
);

-- Vinculo de um tecnico com uma empresa (technician_affiliation.affiliation_type).
CREATE TYPE technical_affiliation_type AS ENUM (
    'INDEPENDENT',
    'AFFILIATED',
    'PARTNER'
);
