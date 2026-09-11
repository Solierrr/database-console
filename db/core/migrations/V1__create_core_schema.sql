-- =============================================================================
-- V1__create_core_schema.sql
--
-- Migration Flyway PROPOSTA para o api-core -- este arquivo NAO existe hoje
-- no repositorio api-core (ele usa ddl-auto=validate sem Flyway). Representa
-- o baseline que deveria ser aplicado caso o api-core adote Flyway,
-- equivalente ao estado atual descrito em db/core/schema.sql + enums.sql.
-- Ate la, e mantido aqui apenas como historico/referencia versionada.
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

-- -----------------------------------------------------------------------------
-- Grupo: localizacao e contato (sem dependencias)
-- -----------------------------------------------------------------------------
CREATE TABLE address (
    id            UUID NOT NULL DEFAULT gen_random_uuid(),
    state         VARCHAR(2) NOT NULL,
    city          VARCHAR(255) NOT NULL,
    neighborhood  VARCHAR(255),
    zip_code      VARCHAR(8) NOT NULL,
    street        VARCHAR(255) NOT NULL,
    number        VARCHAR(10),

    CONSTRAINT pk_address PRIMARY KEY (id)
);

CREATE TABLE business_contact (
    id             UUID NOT NULL DEFAULT gen_random_uuid(),
    company_email  VARCHAR(100) NOT NULL,
    phone          VARCHAR(12),
    website        VARCHAR(255),

    CONSTRAINT pk_business_contact PRIMARY KEY (id)
);

CREATE TABLE contact (
    id     UUID NOT NULL DEFAULT gen_random_uuid(),
    email  VARCHAR(100),
    phone  VARCHAR(12),

    CONSTRAINT pk_contact PRIMARY KEY (id)
);

-- -----------------------------------------------------------------------------
-- Grupo: RBAC (cargos, permissoes) e usuarios (sem dependencias)
-- -----------------------------------------------------------------------------

-- name = sigla do cargo (ex.: "ADMIN"); accesses guarda a lista de escopos
-- liberados para esse cargo (ver constante Position.ADMIN_NAME no codigo).
CREATE TABLE position (
    id        UUID NOT NULL DEFAULT gen_random_uuid(),
    name      VARCHAR(12) NOT NULL,
    accesses  VARCHAR(255) NOT NULL,

    CONSTRAINT pk_position PRIMARY KEY (id)
);

CREATE TABLE permission (
    id               UUID NOT NULL DEFAULT gen_random_uuid(),
    permission_name  VARCHAR(100) NOT NULL,
    name             VARCHAR(150) NOT NULL,
    description      VARCHAR(300) NOT NULL,

    CONSTRAINT pk_permission PRIMARY KEY (id),
    CONSTRAINT uq_permission_permission_name UNIQUE (permission_name)
);

CREATE TABLE profession (
    id                      UUID NOT NULL DEFAULT gen_random_uuid(),
    name                    VARCHAR(100),
    accept_emergency_call   BOOLEAN NOT NULL DEFAULT false,
    requires_registration   BOOLEAN,

    CONSTRAINT pk_profession PRIMARY KEY (id)
);

CREATE TABLE model (
    id           UUID NOT NULL DEFAULT gen_random_uuid(),
    brand        VARCHAR(255) NOT NULL,
    model        VARCHAR(255) NOT NULL,
    power_wp     NUMERIC NOT NULL,
    efficiency   NUMERIC NOT NULL,
    dimension    NUMERIC NOT NULL,
    weight       NUMERIC NOT NULL,
    status       model_status NOT NULL DEFAULT 'UNDER_ANALYSIS',

    CONSTRAINT pk_model PRIMARY KEY (id)
);

CREATE TABLE company_plans (
    id     UUID NOT NULL DEFAULT gen_random_uuid(),
    name   VARCHAR(255) NOT NULL,
    value  NUMERIC NOT NULL,
    cycle  plan_cycle NOT NULL,

    CONSTRAINT pk_company_plans PRIMARY KEY (id)
);

CREATE TABLE certification (
    id           UUID NOT NULL DEFAULT gen_random_uuid(),
    name         VARCHAR(100),
    issuer       VARCHAR(100),
    validity     TIMESTAMP,
    description  TEXT,

    CONSTRAINT pk_certification PRIMARY KEY (id)
);

-- auth_id referencia auth_user.id no banco do api-auth (outro
-- microsservico/banco) -- sem FK real aqui de proposito, so o valor solto.
-- username = handle publico do usuario (ex.: "@joaosilva"), sempre minusculo
-- e distinto do nome legal armazenado em person.name.
CREATE TABLE users (
    id        UUID NOT NULL DEFAULT gen_random_uuid(),
    auth_id   UUID NOT NULL,
    username  VARCHAR(30) NOT NULL,
    avatar    VARCHAR(255),
    banner    VARCHAR(255),
    active    BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uq_users_auth_id UNIQUE (auth_id),
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT ck_users_username_format CHECK (username ~ '^[a-z0-9_]{3,30}$')
);

-- -----------------------------------------------------------------------------
-- Grupo: empresas
-- -----------------------------------------------------------------------------
CREATE TABLE company (
    id                    UUID NOT NULL DEFAULT gen_random_uuid(),
    status                company_status NOT NULL DEFAULT 'UNDER_ANALYSIS',
    fk_address            UUID,
    fk_business_contact   UUID,
    cnpj                  VARCHAR(14) NOT NULL,
    trade_name            VARCHAR(120) NOT NULL,
    corporate_name        VARCHAR(120) NOT NULL,

    CONSTRAINT pk_company PRIMARY KEY (id),
    CONSTRAINT fk_company_address FOREIGN KEY (fk_address)
        REFERENCES address (id),
    CONSTRAINT fk_company_business_contact FOREIGN KEY (fk_business_contact)
        REFERENCES business_contact (id)
);

CREATE TABLE person (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_users    UUID,
    fk_contact  UUID,
    name        VARCHAR(60) NOT NULL,
    cpf         VARCHAR(11) NOT NULL,
    birth_date  DATE NOT NULL,

    CONSTRAINT pk_person PRIMARY KEY (id),
    CONSTRAINT fk_person_users FOREIGN KEY (fk_users)
        REFERENCES users (id),
    CONSTRAINT fk_person_contact FOREIGN KEY (fk_contact)
        REFERENCES contact (id)
);

-- Tabela associativa position <-> permission.
CREATE TABLE position_permission (
    id             UUID NOT NULL DEFAULT gen_random_uuid(),
    id_position    UUID NOT NULL,
    id_permission  UUID NOT NULL,

    CONSTRAINT pk_position_permission PRIMARY KEY (id),
    CONSTRAINT fk_position_permission_position FOREIGN KEY (id_position)
        REFERENCES position (id),
    CONSTRAINT fk_position_permission_permission FOREIGN KEY (id_permission)
        REFERENCES permission (id)
);

CREATE TABLE supplier (
    id             UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_company     UUID NOT NULL,
    status         supplier_status NOT NULL DEFAULT 'ACTIVE',
    business_type  VARCHAR(40),

    CONSTRAINT pk_supplier PRIMARY KEY (id),
    CONSTRAINT fk_supplier_company FOREIGN KEY (fk_company)
        REFERENCES company (id)
);

CREATE TABLE requester (
    id             UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_company     UUID NOT NULL,
    business_type  VARCHAR(40),

    CONSTRAINT pk_requester PRIMARY KEY (id),
    CONSTRAINT fk_requester_company FOREIGN KEY (fk_company)
        REFERENCES company (id)
);

CREATE TABLE technician (
    id         UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_person  UUID NOT NULL,
    crea       VARCHAR(255) NOT NULL,

    CONSTRAINT pk_technician PRIMARY KEY (id),
    CONSTRAINT fk_technician_person FOREIGN KEY (fk_person)
        REFERENCES person (id)
);

-- Tabela associativa company <-> users, com o cargo do usuario na empresa.
CREATE TABLE user_company (
    id            UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_company    UUID NOT NULL,
    fk_users      UUID NOT NULL,
    fk_position   UUID NOT NULL,

    CONSTRAINT pk_user_company PRIMARY KEY (id),
    CONSTRAINT fk_user_company_company FOREIGN KEY (fk_company)
        REFERENCES company (id),
    CONSTRAINT fk_user_company_users FOREIGN KEY (fk_users)
        REFERENCES users (id),
    CONSTRAINT fk_user_company_position FOREIGN KEY (fk_position)
        REFERENCES position (id)
);

-- Tabela associativa company <-> position (cargos disponiveis por empresa).
CREATE TABLE company_positions (
    id           UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_company   UUID NOT NULL,
    fk_position  UUID NOT NULL,

    CONSTRAINT pk_company_positions PRIMARY KEY (id),
    CONSTRAINT fk_company_positions_company FOREIGN KEY (fk_company)
        REFERENCES company (id),
    CONSTRAINT fk_company_positions_position FOREIGN KEY (fk_position)
        REFERENCES position (id)
);

-- -----------------------------------------------------------------------------
-- Grupo: qualificacao profissional
-- -----------------------------------------------------------------------------
CREATE TABLE professional_registration (
    id               UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_technician    UUID,
    fk_profession    UUID,
    council          VARCHAR(60),
    number           VARCHAR(30),
    expiration_date  TIMESTAMP,

    CONSTRAINT pk_professional_registration PRIMARY KEY (id),
    CONSTRAINT fk_professional_registration_technician FOREIGN KEY (fk_technician)
        REFERENCES technician (id),
    CONSTRAINT fk_professional_registration_profession FOREIGN KEY (fk_profession)
        REFERENCES profession (id)
);

-- Tabela associativa professional_registration <-> certification.
CREATE TABLE certification_record (
    id                              UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_professional_registration    UUID,
    fk_certification                UUID,

    CONSTRAINT pk_certification_record PRIMARY KEY (id),
    CONSTRAINT fk_certification_record_registration FOREIGN KEY (fk_professional_registration)
        REFERENCES professional_registration (id),
    CONSTRAINT fk_certification_record_certification FOREIGN KEY (fk_certification)
        REFERENCES certification (id)
);

CREATE TABLE technician_affiliation (
    id                UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_company        UUID,
    fk_technician     UUID NOT NULL,
    affiliation_type  technical_affiliation_type NOT NULL,
    active            BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT pk_technician_affiliation PRIMARY KEY (id),
    CONSTRAINT fk_technician_affiliation_company FOREIGN KEY (fk_company)
        REFERENCES company (id),
    CONSTRAINT fk_technician_affiliation_technician FOREIGN KEY (fk_technician)
        REFERENCES technician (id)
);

CREATE TABLE shift (
    id             UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_technician  UUID NOT NULL,
    day_week       day_week NOT NULL,
    start_date     TIMESTAMP NOT NULL,
    end_date       TIMESTAMP NOT NULL,

    CONSTRAINT pk_shift PRIMARY KEY (id),
    CONSTRAINT fk_shift_technician FOREIGN KEY (fk_technician)
        REFERENCES technician (id),
    CONSTRAINT ck_shift_period CHECK (end_date > start_date)
);

-- -----------------------------------------------------------------------------
-- Grupo: assinatura e cobranca (planos da plataforma, nao do cliente final)
-- -----------------------------------------------------------------------------
CREATE TABLE subscription (
    id             UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_supplier    UUID NOT NULL,
    fk_plan        UUID NOT NULL,
    status         subscription_status NOT NULL DEFAULT 'PAID',
    auto_renewal   BOOLEAN NOT NULL DEFAULT true,
    start_date     TIMESTAMPTZ NOT NULL,
    end_date       TIMESTAMPTZ,

    CONSTRAINT pk_subscription PRIMARY KEY (id),
    CONSTRAINT fk_subscription_supplier FOREIGN KEY (fk_supplier)
        REFERENCES supplier (id),
    CONSTRAINT fk_subscription_plan FOREIGN KEY (fk_plan)
        REFERENCES company_plans (id)
);

CREATE TABLE charge (
    id               UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_subscription  UUID NOT NULL,
    amount           NUMERIC NOT NULL,
    payment_method   payment_method NOT NULL,
    status           billing_status NOT NULL DEFAULT 'PENDING',
    due_date         DATE NOT NULL,
    payment_date     TIMESTAMPTZ,

    CONSTRAINT pk_charge PRIMARY KEY (id),
    CONSTRAINT fk_charge_subscription FOREIGN KEY (fk_subscription)
        REFERENCES subscription (id)
);

-- -----------------------------------------------------------------------------
-- Grupo: catalogo de fornecedores (ofertas e estoque de modelos de painel)
-- -----------------------------------------------------------------------------
CREATE TABLE offer (
    id                UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_supplier       UUID NOT NULL,
    fk_model          UUID NOT NULL,
    unit_price        NUMERIC NOT NULL,
    availability      INTEGER NOT NULL,
    expiration_date   TIMESTAMPTZ,

    CONSTRAINT pk_offer PRIMARY KEY (id),
    CONSTRAINT fk_offer_supplier FOREIGN KEY (fk_supplier)
        REFERENCES supplier (id),
    CONSTRAINT fk_offer_model FOREIGN KEY (fk_model)
        REFERENCES model (id),
    CONSTRAINT ck_offer_availability CHECK (availability >= 0)
);

CREATE TABLE inventory (
    id           UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_supplier  UUID NOT NULL,
    fk_model     UUID NOT NULL,
    quantity     INTEGER NOT NULL,

    CONSTRAINT pk_inventory PRIMARY KEY (id),
    CONSTRAINT fk_inventory_supplier FOREIGN KEY (fk_supplier)
        REFERENCES supplier (id),
    CONSTRAINT fk_inventory_model FOREIGN KEY (fk_model)
        REFERENCES model (id),
    CONSTRAINT ck_inventory_quantity CHECK (quantity >= 0)
);

-- -----------------------------------------------------------------------------
-- Grupo: unidades do requester (locais de instalacao)
-- -----------------------------------------------------------------------------
CREATE TABLE geolocalization (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_address  UUID,
    latitude    NUMERIC(10, 7) NOT NULL,
    longitude   NUMERIC(10, 7) NOT NULL,

    CONSTRAINT pk_geolocalization PRIMARY KEY (id),
    CONSTRAINT fk_geolocalization_address FOREIGN KEY (fk_address)
        REFERENCES address (id)
);

CREATE TABLE local_unit (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_requester    UUID NOT NULL,
    fk_address      UUID,
    complement      VARCHAR(255),
    location_type   location_type NOT NULL,

    CONSTRAINT pk_local_unit PRIMARY KEY (id),
    CONSTRAINT fk_local_unit_requester FOREIGN KEY (fk_requester)
        REFERENCES requester (id),
    CONSTRAINT fk_local_unit_address FOREIGN KEY (fk_address)
        REFERENCES address (id)
);

CREATE TABLE unit_specifications (
    id               UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_local_unit    UUID NOT NULL,
    specifications   VARCHAR(255),
    location_photos  VARCHAR(255),
    date             TIMESTAMPTZ NOT NULL,

    CONSTRAINT pk_unit_specifications PRIMARY KEY (id),
    CONSTRAINT fk_unit_specifications_local_unit FOREIGN KEY (fk_local_unit)
        REFERENCES local_unit (id)
);

-- -----------------------------------------------------------------------------
-- Grupo: execucao de servico (projeto -> servico -> contrato/executores)
-- -----------------------------------------------------------------------------
CREATE TABLE technical_project (
    id            UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_requester  UUID,
    fk_local_unit UUID,
    status        service_status,
    start_date    TIMESTAMPTZ,
    end_date      TIMESTAMP,

    CONSTRAINT pk_technical_project PRIMARY KEY (id),
    CONSTRAINT fk_technical_project_requester FOREIGN KEY (fk_requester)
        REFERENCES requester (id),
    CONSTRAINT fk_technical_project_local_unit FOREIGN KEY (fk_local_unit)
        REFERENCES local_unit (id)
);

-- accepted_by guarda o id do tecnico/usuario que aceitou o servico como um
-- UUID solto (sem FK) -- assim esta modelado hoje em api-core.
CREATE TABLE technical_service (
    id                    UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_technical_project  UUID NOT NULL,
    purpose               VARCHAR(255) NOT NULL,
    status                service_status NOT NULL DEFAULT 'OPEN',
    scheduled_date        TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    accepted_by           UUID,
    accepted_at           TIMESTAMPTZ,
    end_date              TIMESTAMPTZ,

    CONSTRAINT pk_technical_service PRIMARY KEY (id),
    CONSTRAINT fk_technical_service_project FOREIGN KEY (fk_technical_project)
        REFERENCES technical_project (id)
);

-- 1:1 com technical_service (UNIQUE em fk_service) -- a entidade Java usa
-- @OneToOne mas nao declarava unique=true explicitamente; adicionado aqui
-- para garantir a cardinalidade real no banco.
CREATE TABLE service_contract (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_service          UUID NOT NULL,
    warranty            VARCHAR(255),
    delivery_deadline   DATE,
    insurance           BOOLEAN NOT NULL DEFAULT false,
    utility_approval    BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT pk_service_contract PRIMARY KEY (id),
    CONSTRAINT uq_service_contract_service UNIQUE (fk_service),
    CONSTRAINT fk_service_contract_service FOREIGN KEY (fk_service)
        REFERENCES technical_service (id)
);

CREATE TABLE service_executor (
    id                          UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_service                  UUID NOT NULL,
    fk_technician_affiliation   UUID NOT NULL,
    function                    VARCHAR(255) NOT NULL,

    CONSTRAINT pk_service_executor PRIMARY KEY (id),
    CONSTRAINT fk_service_executor_service FOREIGN KEY (fk_service)
        REFERENCES technical_service (id),
    CONSTRAINT fk_service_executor_affiliation FOREIGN KEY (fk_technician_affiliation)
        REFERENCES technician_affiliation (id)
);

-- Um requester so pode avaliar o mesmo tecnico uma vez por servico.
CREATE TABLE professional_review (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_professional UUID NOT NULL,
    fk_reviewer     UUID NOT NULL,
    fk_service      UUID NOT NULL,
    rating          NUMERIC(2, 1) NOT NULL,
    comment         VARCHAR(255),
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_professional_review PRIMARY KEY (id),
    CONSTRAINT fk_professional_review_professional FOREIGN KEY (fk_professional)
        REFERENCES technician (id),
    CONSTRAINT fk_professional_review_reviewer FOREIGN KEY (fk_reviewer)
        REFERENCES users (id),
    CONSTRAINT fk_professional_review_service FOREIGN KEY (fk_service)
        REFERENCES technical_service (id),
    CONSTRAINT uq_professional_review_reviewer_professional_service
        UNIQUE (fk_reviewer, fk_professional, fk_service),
    CONSTRAINT ck_professional_review_rating CHECK (rating BETWEEN 0 AND 5)
);

CREATE TABLE energy_bill (
    id             UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_local_unit  UUID NOT NULL,
    consumption    NUMERIC NOT NULL,
    price          NUMERIC NOT NULL,

    CONSTRAINT pk_energy_bill PRIMARY KEY (id),
    CONSTRAINT fk_energy_bill_local_unit FOREIGN KEY (fk_local_unit)
        REFERENCES local_unit (id)
);

CREATE TABLE technical_course (
    id           UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_company   UUID,
    title        VARCHAR(30),
    information  TEXT,
    link         TEXT,

    CONSTRAINT pk_technical_course PRIMARY KEY (id),
    CONSTRAINT fk_technical_course_company FOREIGN KEY (fk_company)
        REFERENCES company (id)
);

-- -----------------------------------------------------------------------------
-- Grupo: propostas comerciais (requester <- oferta de fornecedor)
-- -----------------------------------------------------------------------------
CREATE TABLE proposal (
    id            UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_requester  UUID NOT NULL,
    status        proposal_status NOT NULL DEFAULT 'AWAITING_SUPPLIER',
    notes         VARCHAR(255),
    total_amount  NUMERIC,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ,

    CONSTRAINT pk_proposal PRIMARY KEY (id),
    CONSTRAINT fk_proposal_requester FOREIGN KEY (fk_requester)
        REFERENCES requester (id)
);

CREATE TABLE proposal_item (
    id                UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_proposal       UUID NOT NULL,
    fk_offer          UUID NOT NULL,
    quantity          INTEGER NOT NULL,
    negotiated_price  NUMERIC,
    discount          NUMERIC,

    CONSTRAINT pk_proposal_item PRIMARY KEY (id),
    CONSTRAINT fk_proposal_item_proposal FOREIGN KEY (fk_proposal)
        REFERENCES proposal (id),
    CONSTRAINT fk_proposal_item_offer FOREIGN KEY (fk_offer)
        REFERENCES offer (id),
    CONSTRAINT ck_proposal_item_quantity CHECK (quantity > 0)
);

CREATE TABLE proposal_unit (
    id                 UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_proposal_item   UUID NOT NULL,
    fk_local_unit      UUID NOT NULL,
    quantity           INTEGER NOT NULL,
    note               VARCHAR(255),

    CONSTRAINT pk_proposal_unit PRIMARY KEY (id),
    CONSTRAINT fk_proposal_unit_proposal_item FOREIGN KEY (fk_proposal_item)
        REFERENCES proposal_item (id),
    CONSTRAINT fk_proposal_unit_local_unit FOREIGN KEY (fk_local_unit)
        REFERENCES local_unit (id),
    CONSTRAINT ck_proposal_unit_quantity CHECK (quantity > 0)
);

-- -----------------------------------------------------------------------------
-- Grupo: auditoria de acoes de usuario
-- -----------------------------------------------------------------------------
CREATE TABLE flux_log (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_user     UUID NOT NULL,
    action      VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_flux_log PRIMARY KEY (id),
    CONSTRAINT fk_flux_log_user FOREIGN KEY (fk_user)
        REFERENCES users (id)
);
