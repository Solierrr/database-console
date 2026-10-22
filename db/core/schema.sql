-- =============================================================================
-- db/core/schema.sql
--
-- Snapshot consolidado do schema do api-core (com.solaria.persistence):
-- empresas, catalogo de fornecedores, propostas, tecnicos e execucao de
-- servico. Reconstruido a partir das 40 entidades JPA em
-- api-core/src/main/java/com/solaria/persistence/domain/entity/.
--
-- IMPORTANTE: api-core roda com ddl-auto=validate e nao possui Flyway nem
-- schema.sql proprio -- este arquivo E a fonte de verdade versionada do
-- schema, ate que o api-core adote migrations. Toda mudanca em uma @Entity
-- do api-core precisa ser refletida aqui manualmente, incluindo em
-- db/core/migrations/.
--
-- Nenhuma @Entity do api-core declara ON DELETE/ON UPDATE (Hibernate nao
-- gera essas clausulas a partir de @ManyToOne puro); as FKs abaixo usam
-- NO ACTION por padrao. Ajuste caso uma regra de negocio real exija cascade.
--
-- Pre-requisito: db/core/enums.sql (extensao pgcrypto e tipos ENUM).
-- Ordem das tabelas = ordem topologica de dependencia de FK.
-- =============================================================================

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
    fk_owner_company UUID,

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
    accesses  VARCHAR(255),

    CONSTRAINT pk_position PRIMARY KEY (id),
    CONSTRAINT uq_position_name UNIQUE (name)
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

CREATE TABLE brand (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_owner_company UUID,
    name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    visibility VARCHAR(16) NOT NULL DEFAULT 'PRIVATE' CHECK (visibility IN ('PRIVATE','PUBLIC')),
    archived BOOLEAN NOT NULL DEFAULT false,
    legacy BOOLEAN NOT NULL DEFAULT false,
    logo_url VARCHAR(2048), reference_url VARCHAR(2048),
    revision BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_brand_public_active CHECK (visibility <> 'PUBLIC' OR NOT archived),
    CONSTRAINT ck_brand_owner CHECK (fk_owner_company IS NOT NULL OR legacy OR visibility = 'PUBLIC')
);
CREATE UNIQUE INDEX uq_brand_public_name ON brand(normalized_name) WHERE visibility = 'PUBLIC';
CREATE UNIQUE INDEX uq_brand_private_company_name ON brand(fk_owner_company,normalized_name) WHERE visibility = 'PRIVATE' AND NOT archived;

CREATE TABLE model (
    id           UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_brand     UUID NOT NULL REFERENCES brand(id),
    model        VARCHAR(255) NOT NULL,
    power_wp     NUMERIC,
    efficiency   NUMERIC,
    dimension    NUMERIC,
    type         VARCHAR(32),
    width        NUMERIC,
    length       NUMERIC,
    weight       NUMERIC,
    status       model_status NOT NULL DEFAULT 'UNDER_ANALYSIS',
    product_type VARCHAR(16) NOT NULL DEFAULT 'PANEL',
    infrastructure_type VARCHAR(16),
    material     VARCHAR(64),

    CONSTRAINT pk_model PRIMARY KEY (id),
    CONSTRAINT ck_model_type CHECK (type IS NULL OR type IN ('MONOCRYSTALLINE', 'POLYCRYSTALLINE', 'THIN_FILM')),
    CONSTRAINT ck_model_product_type CHECK (product_type IN ('PANEL', 'INFRASTRUCTURE')),
    CONSTRAINT ck_model_infrastructure_type CHECK (infrastructure_type IS NULL OR infrastructure_type IN ('RAIL', 'CLAMP', 'BRACKET', 'HOOK', 'KIT', 'OTHER')),
    CONSTRAINT ck_model_panel_fields CHECK (
        product_type <> 'PANEL'
        OR (power_wp IS NOT NULL AND efficiency IS NOT NULL AND type IS NOT NULL AND width IS NOT NULL AND length IS NOT NULL AND weight IS NOT NULL AND infrastructure_type IS NULL)
    ),
    CONSTRAINT ck_model_infrastructure_fields CHECK (
        product_type <> 'INFRASTRUCTURE'
        OR (infrastructure_type IS NOT NULL AND power_wp IS NULL AND efficiency IS NULL AND type IS NULL)
    )
);
CREATE INDEX idx_model_product_type ON model (product_type);

CREATE TABLE company_plans (
    id     UUID NOT NULL DEFAULT gen_random_uuid(),
    name   VARCHAR(255) NOT NULL,
    value  NUMERIC NOT NULL,
    cycle  plan_cycle NOT NULL,

    CONSTRAINT pk_company_plans PRIMARY KEY (id)
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
    connections UUID[] NOT NULL DEFAULT ARRAY[]::uuid[],

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
    type                  VARCHAR(16) NOT NULL CHECK (type IN ('SUPPLIER', 'DEMANDANT')),
    fk_address            UUID,
    fk_business_contact   UUID,
    cnpj                  VARCHAR(14) NOT NULL,
    trade_name            VARCHAR(120) NOT NULL,
    corporate_name        VARCHAR(120) NOT NULL,
    slug                  VARCHAR(160) NOT NULL UNIQUE,

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

-- Marca uma empresa como prestadora de servico tecnico (alem de
-- fornecedora/solicitante). Sem seed proprio ainda -- ver acompanhamento.
CREATE TABLE technical_company (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_company  UUID NOT NULL,

    CONSTRAINT pk_technical_company PRIMARY KEY (id),
    CONSTRAINT fk_technical_company_company FOREIGN KEY (fk_company)
        REFERENCES company (id)
);

CREATE TABLE technician (
    id         UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_person  UUID NOT NULL,
    crea       VARCHAR(255) NOT NULL,
    slug       VARCHAR(160) NOT NULL UNIQUE,

    CONSTRAINT pk_technician PRIMARY KEY (id),
    CONSTRAINT fk_technician_person FOREIGN KEY (fk_person)
        REFERENCES person (id)
);

-- Certificacao tecnica de um tecnico especifico (ex.: NR-10, NR-35).
-- "type" e o rotulo curto/categoria; "name"/"issuer" sao complementares.
CREATE TABLE certification (
    id             UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_technician  UUID,
    type           VARCHAR(255),
    information    TEXT,
    image          TEXT,
    description    TEXT,
    issuer         VARCHAR(100),
    name           VARCHAR(100),
    validity       TIMESTAMP,

    CONSTRAINT pk_certification PRIMARY KEY (id),
    CONSTRAINT fk_certification_technician FOREIGN KEY (fk_technician)
        REFERENCES technician (id)
);

-- Tabela associativa company <-> users, com o cargo do usuario na empresa.
CREATE TABLE user_company (
    id            UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_company    UUID NOT NULL,
    fk_users      UUID NOT NULL,
    fk_position   UUID NOT NULL,

    CONSTRAINT pk_user_company PRIMARY KEY (id),
    CONSTRAINT uq_user_company_user UNIQUE (fk_users),
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
    fk_company        UUID NOT NULL,
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
    slug              VARCHAR(160) NOT NULL UNIQUE,
    discount_percentage NUMERIC,
    source_locale     VARCHAR(10),
    translation_status VARCHAR(32) NOT NULL DEFAULT 'PENDING',

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
    fk_address      UUID NOT NULL,
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
    fk_requester  UUID NOT NULL,
    fk_local_unit UUID NOT NULL,
    status        service_status NOT NULL DEFAULT 'OPEN',
    start_date    TIMESTAMPTZ NOT NULL DEFAULT now(),
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
    photo_url      VARCHAR(255),
    photo_public_id VARCHAR(255),

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
    fk_supplier   UUID,
    status        proposal_status NOT NULL DEFAULT 'AWAITING_SUPPLIER',
    notes         VARCHAR(500),
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

-- Catalogo traduzido e fotos usadas pelas entidades atuais do api-core.
CREATE TABLE offer_service_region (
    fk_offer UUID NOT NULL REFERENCES offer(id),
    region VARCHAR(120)
);
CREATE INDEX idx_offer_service_region_offer ON offer_service_region (fk_offer);

CREATE TABLE offer_translation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_offer UUID NOT NULL REFERENCES offer(id),
    locale VARCHAR(10) NOT NULL,
    title VARCHAR(160) NOT NULL,
    description TEXT NOT NULL,
    details TEXT,
    CONSTRAINT uq_offer_translation_locale UNIQUE (fk_offer, locale)
);

CREATE TABLE model_photo (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_model UUID NOT NULL REFERENCES model(id),
    url VARCHAR(255) NOT NULL,
    public_id VARCHAR(255) NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_model_photo_model_created ON model_photo (fk_model, created_at DESC);
CREATE UNIQUE INDEX uq_model_photo_primary ON model_photo (fk_model) WHERE is_primary;

CREATE TABLE company_photo (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_company UUID NOT NULL REFERENCES company(id),
    type VARCHAR(255) NOT NULL CHECK (type IN ('PROFILE', 'BANNER')),
    url VARCHAR(255) NOT NULL,
    public_id VARCHAR(255) NOT NULL,
    crop_x INTEGER,
    crop_y INTEGER,
    crop_width INTEGER,
    crop_height INTEGER,
    CONSTRAINT ck_company_photo_crop CHECK (
        (crop_x IS NULL AND crop_y IS NULL AND crop_width IS NULL AND crop_height IS NULL)
        OR (crop_x IS NOT NULL AND crop_y IS NOT NULL AND crop_width IS NOT NULL AND crop_height IS NOT NULL
        AND crop_x >= 0 AND crop_y >= 0 AND crop_width > 0 AND crop_height > 0)
    ),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE user_photo (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_user UUID NOT NULL REFERENCES users(id),
    type VARCHAR(255) NOT NULL CHECK (type IN ('PROFILE', 'BANNER')),
    url VARCHAR(255) NOT NULL,
    public_id VARCHAR(255) NOT NULL,
    crop_x INTEGER,
    crop_y INTEGER,
    crop_width INTEGER,
    crop_height INTEGER,
    CONSTRAINT ck_user_photo_crop CHECK (
        (crop_x IS NULL AND crop_y IS NULL AND crop_width IS NULL AND crop_height IS NULL)
        OR (crop_x IS NOT NULL AND crop_y IS NOT NULL AND crop_width IS NOT NULL AND crop_height IS NOT NULL
        AND crop_x >= 0 AND crop_y >= 0 AND crop_width > 0 AND crop_height > 0)
    ),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE local_unit_photo (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_local_unit UUID NOT NULL REFERENCES local_unit(id),
    type VARCHAR(16) NOT NULL DEFAULT 'GALLERY' CONSTRAINT ck_local_unit_photo_type CHECK (type IN ('MAIN', 'BANNER', 'GALLERY')),
    url VARCHAR(255) NOT NULL,
    public_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE UNIQUE INDEX uq_local_unit_photo_main ON local_unit_photo (fk_local_unit) WHERE type = 'MAIN';
CREATE UNIQUE INDEX uq_local_unit_photo_banner ON local_unit_photo (fk_local_unit) WHERE type = 'BANNER';

-- Códigos de acesso: convite de funcionário sem envio de e-mail.
CREATE TABLE access_code (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_company  UUID NOT NULL,
    fk_position UUID NOT NULL,
    code        VARCHAR(12) NOT NULL,
    status      VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_access_code PRIMARY KEY (id),
    CONSTRAINT uq_access_code_code UNIQUE (code),
    CONSTRAINT fk_access_code_company FOREIGN KEY (fk_company)
        REFERENCES company (id),
    CONSTRAINT fk_access_code_position FOREIGN KEY (fk_position)
        REFERENCES position (id),
    CONSTRAINT ck_access_code_status CHECK (status IN ('ACTIVE', 'USED', 'REVOKED'))
);
CREATE INDEX idx_access_code_company ON access_code (fk_company);

-- Admin Solaria: super-admin de plataforma, desacoplado de user_company/position.
CREATE TABLE platform_admin (
    id         UUID NOT NULL DEFAULT gen_random_uuid(),
    fk_user    UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_platform_admin PRIMARY KEY (id),
    CONSTRAINT uq_platform_admin_user UNIQUE (fk_user),
    CONSTRAINT fk_platform_admin_user FOREIGN KEY (fk_user)
        REFERENCES users (id)
);

ALTER TABLE model ADD COLUMN IF NOT EXISTS fk_creator_company UUID REFERENCES company(id);
ALTER TABLE technician ADD COLUMN IF NOT EXISTS status VARCHAR(24) NOT NULL DEFAULT 'UNDER_ANALYSIS';
CREATE TABLE IF NOT EXISTS professional_onboarding (
    id UUID PRIMARY KEY, auth_id UUID NOT NULL UNIQUE, user_id UUID NOT NULL REFERENCES users(id),
    technician_id UUID REFERENCES technician(id), revision BIGINT NOT NULL DEFAULT 0,
    approved_version BIGINT NOT NULL DEFAULT 0, draft_json TEXT NOT NULL DEFAULT '{}',
    approved_json TEXT, suspended BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS professional_document (
    id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id), kind VARCHAR(20) NOT NULL,
    content_type VARCHAR(30) NOT NULL, sha256 VARCHAR(64) NOT NULL, content BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_professional_document_user ON professional_document(user_id);
CREATE TABLE IF NOT EXISTS professional_submission (
    id UUID PRIMARY KEY, onboarding_id UUID NOT NULL REFERENCES professional_onboarding(id),
    revision BIGINT NOT NULL, base_approved_version BIGINT NOT NULL, snapshot_json TEXT NOT NULL,
    policy_json TEXT NOT NULL, status VARCHAR(30) NOT NULL, result_json TEXT, attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL, decided_at TIMESTAMPTZ,
    decided_by UUID REFERENCES users(id), decision_origin VARCHAR(10), decision_reason TEXT,
    UNIQUE(onboarding_id, revision)
);
CREATE INDEX IF NOT EXISTS idx_professional_submission_work ON professional_submission(status, available_at);
ALTER TABLE technician ALTER COLUMN crea DROP NOT NULL;

ALTER TABLE profession ADD COLUMN IF NOT EXISTS requires_nr10 boolean;
ALTER TABLE profession ADD COLUMN IF NOT EXISTS requires_nr35 boolean;

ALTER TABLE professional_document ALTER COLUMN content DROP NOT NULL;
ALTER TABLE professional_document ADD COLUMN IF NOT EXISTS cloudinary_public_id VARCHAR(255);
ALTER TABLE professional_document ADD COLUMN IF NOT EXISTS cloudinary_format VARCHAR(20);


DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM inventory GROUP BY fk_supplier, fk_model HAVING count(*) > 1) THEN
        RAISE EXCEPTION 'Duplicate inventory supplier/model pairs; reconcile verified records before V13';
    END IF;
END $$;

ALTER TABLE inventory ADD CONSTRAINT uq_inventory_supplier_model UNIQUE (fk_supplier, fk_model);
ALTER TABLE offer ADD CONSTRAINT ck_offer_unit_price CHECK (unit_price > 0);
ALTER TABLE offer ADD CONSTRAINT ck_offer_discount CHECK (discount_percentage BETWEEN 0 AND 100);
ALTER TABLE offer ADD CONSTRAINT ck_offer_translation_status CHECK (translation_status IN ('PENDING', 'COMPLETED', 'FAILED'));
ALTER TABLE professional_document ADD CONSTRAINT ck_professional_document_storage CHECK (
    (content IS NOT NULL AND octet_length(content) > 0 AND cloudinary_public_id IS NULL AND cloudinary_format IS NULL)
    OR (content IS NULL AND cloudinary_public_id IS NOT NULL AND length(trim(cloudinary_public_id)) > 0
        AND cloudinary_format IS NOT NULL AND length(trim(cloudinary_format)) > 0)
);
ALTER TABLE professional_submission ADD CONSTRAINT ck_professional_submission_status
    CHECK (status IN ('QUEUED', 'VALIDATING', 'RETRY_PENDING', 'MANUAL_REVIEW', 'APPROVED', 'REJECTED', 'SUSPENDED', 'REINSTATED'));
ALTER TABLE professional_submission ADD CONSTRAINT ck_professional_submission_attempts CHECK (attempts >= 0);


CREATE TABLE offer_translation_job (
    id UUID PRIMARY KEY,
    offer_id UUID NOT NULL REFERENCES offer(id) ON DELETE CASCADE,
    source_translation_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED',
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    claim_token UUID,
    error_code VARCHAR(40),
    CONSTRAINT uq_offer_translation_job_source UNIQUE (offer_id, source_translation_id),
    CONSTRAINT ck_offer_translation_job_status CHECK (status IN ('QUEUED','PROCESSING','RETRY_PENDING','COMPLETED','FAILED','CANCELLED')),
    CONSTRAINT ck_offer_translation_job_attempts CHECK (attempts >= 0)
);
CREATE INDEX idx_offer_translation_job_available ON offer_translation_job (available_at, id)
    WHERE status IN ('QUEUED', 'PROCESSING', 'RETRY_PENDING');
INSERT INTO offer_translation_job(id,offer_id,source_translation_id)
SELECT gen_random_uuid(), o.id, t.id FROM offer o JOIN offer_translation t ON t.fk_offer=o.id
WHERE t.locale='und' AND o.translation_status IN ('PENDING','FAILED');


ALTER TABLE offer ADD COLUMN commercial_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE offer ADD CONSTRAINT ck_offer_commercial_status CHECK (commercial_status IN ('ACTIVE','PAUSED','CLOSED'));
CREATE TABLE offer_status_history (
    id UUID PRIMARY KEY, offer_id UUID NOT NULL REFERENCES offer(id),
    previous_status VARCHAR(16) NOT NULL CHECK (previous_status IN ('ACTIVE','PAUSED','CLOSED')),
    new_status VARCHAR(16) NOT NULL CHECK (new_status IN ('ACTIVE','PAUSED','CLOSED')),
    actor_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_offer_history_transition CHECK (previous_status <> new_status)
);
CREATE INDEX idx_offer_status_history_offer ON offer_status_history(offer_id, created_at DESC);


CREATE TABLE professional_team (
    id UUID PRIMARY KEY, company_id UUID NOT NULL REFERENCES company(id),
    name VARCHAR(100) NOT NULL CHECK (length(trim(name)) > 0),
    responsible_id UUID NOT NULL REFERENCES technician(id),
    active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE professional_team_member (
    id UUID PRIMARY KEY, team_id UUID NOT NULL REFERENCES professional_team(id) ON DELETE CASCADE,
    technician_id UUID NOT NULL REFERENCES technician(id),
    CONSTRAINT uq_professional_team_member UNIQUE(team_id, technician_id)
);
CREATE INDEX idx_professional_team_company ON professional_team(company_id);
CREATE INDEX idx_professional_team_member_technician ON professional_team_member(technician_id);


CREATE INDEX IF NOT EXISTS idx_user_company_company ON user_company (fk_company);
CREATE INDEX IF NOT EXISTS idx_supplier_company ON supplier (fk_company);
CREATE INDEX IF NOT EXISTS idx_requester_company ON requester (fk_company);
CREATE INDEX IF NOT EXISTS idx_address_owner_company ON address (fk_owner_company);
CREATE INDEX IF NOT EXISTS idx_offer_supplier ON offer (fk_supplier);
CREATE INDEX IF NOT EXISTS idx_offer_model ON offer (fk_model);
CREATE INDEX IF NOT EXISTS idx_subscription_supplier ON subscription (fk_supplier);
CREATE INDEX IF NOT EXISTS idx_charge_subscription ON charge (fk_subscription);
CREATE INDEX IF NOT EXISTS idx_local_unit_requester ON local_unit (fk_requester);
CREATE INDEX IF NOT EXISTS idx_technical_project_requester ON technical_project (fk_requester);
CREATE INDEX IF NOT EXISTS idx_proposal_requester ON proposal (fk_requester);
CREATE INDEX IF NOT EXISTS idx_proposal_item_proposal ON proposal_item (fk_proposal);
CREATE INDEX IF NOT EXISTS idx_proposal_item_offer ON proposal_item (fk_offer);
CREATE INDEX IF NOT EXISTS idx_technical_service_project ON technical_service (fk_technical_project);
CREATE INDEX IF NOT EXISTS idx_service_executor_service ON service_executor (fk_service);
CREATE INDEX IF NOT EXISTS idx_technician_person ON technician (fk_person);
CREATE INDEX IF NOT EXISTS idx_professional_registration_technician ON professional_registration (fk_technician);
CREATE INDEX IF NOT EXISTS idx_technician_affiliation_technician ON technician_affiliation (fk_technician);
CREATE INDEX IF NOT EXISTS idx_shift_technician ON shift (fk_technician);
CREATE INDEX IF NOT EXISTS idx_professional_review_professional ON professional_review (fk_professional, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_flux_log_user ON flux_log (fk_user, created_at DESC);


INSERT INTO permission (id, permission_name, name, description)
SELECT gen_random_uuid(), v.permission_name, v.name, v.description
FROM (VALUES
    ('PATCH /api/offers/{id}/status', 'Alterar situação da oferta', 'Pausar, retomar ou encerrar ofertas próprias'),
    ('GET /api/offers/{id}/history', 'Ver histórico de ofertas', 'Consultar alterações de situação das ofertas próprias'),
    ('POST /api/professional-teams', 'Criar equipes profissionais', 'Criar equipes vinculadas à própria empresa'),
    ('PUT /api/professional-teams/{id}', 'Editar equipes profissionais', 'Atualizar integrantes e responsável de equipes próprias'),
    ('GET /api/professional-teams/company/{companyId}', 'Ver equipes profissionais', 'Consultar equipes da própria empresa')
) AS v(permission_name, name, description)
WHERE NOT EXISTS (SELECT 1 FROM permission p WHERE p.permission_name = v.permission_name);

CREATE TABLE brand_request (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_brand UUID NOT NULL REFERENCES brand(id),
    fk_requester_company UUID REFERENCES company(id), fk_requester_user UUID REFERENCES users(id),
    kind VARCHAR(16) NOT NULL CHECK (kind IN ('PUBLICATION','CORRECTION')),
    status VARCHAR(16) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','REJECTED','CANCELLED')),
    proposed_name VARCHAR(255) NOT NULL, proposed_logo_url VARCHAR(2048), proposed_reference_url VARCHAR(2048),
    fk_result_brand UUID REFERENCES brand(id), decision_reason VARCHAR(2000),
    fk_decided_by UUID REFERENCES users(id), decided_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revision BIGINT NOT NULL DEFAULT 0,
    CONSTRAINT ck_brand_rejection_reason CHECK (status <> 'REJECTED' OR length(trim(decision_reason)) > 0 AND decision_reason IS NOT NULL)
);
CREATE UNIQUE INDEX uq_brand_pending_request ON brand_request(fk_brand) WHERE status = 'PENDING';
CREATE INDEX ix_brand_request_company ON brand_request(fk_requester_company, created_at DESC);
ALTER TABLE brand ADD CONSTRAINT fk_brand_owner_company FOREIGN KEY (fk_owner_company) REFERENCES company(id);

-- Document viewer formats and original filenames (V22).
ALTER TABLE professional_document ALTER COLUMN content_type TYPE VARCHAR(100);
ALTER TABLE professional_document ADD COLUMN IF NOT EXISTS original_file_name VARCHAR(255);

-- Project workspace (V24)
-- Projects support company/professional ownership; preserve existing technical-service references.
ALTER TABLE technical_project ALTER COLUMN fk_requester DROP NOT NULL;
ALTER TABLE technical_project ALTER COLUMN fk_local_unit DROP NOT NULL;
ALTER TABLE technical_project ALTER COLUMN start_date DROP NOT NULL;
ALTER TABLE technical_project ADD COLUMN name varchar(160) NOT NULL DEFAULT 'Projeto técnico', ADD COLUMN description text, ADD COLUMN owner_company_id uuid REFERENCES company(id), ADD COLUMN owner_user_id uuid REFERENCES users(id), ADD COLUMN created_by uuid REFERENCES users(id), ADD COLUMN archived boolean NOT NULL DEFAULT false, ADD COLUMN created_at timestamptz NOT NULL DEFAULT now(), ADD COLUMN version bigint NOT NULL DEFAULT 0,
 ADD COLUMN location_state varchar(2), ADD COLUMN location_city varchar(120), ADD COLUMN location_neighborhood varchar(120), ADD COLUMN location_zip_code varchar(8), ADD COLUMN location_street varchar(180), ADD COLUMN location_number varchar(30), ADD COLUMN location_complement varchar(180);
UPDATE technical_project p SET owner_company_id=r.fk_company FROM requester r WHERE r.id=p.fk_requester;
ALTER TABLE technical_project ADD CONSTRAINT ck_project_owner CHECK ((owner_company_id IS NOT NULL)::integer + (owner_user_id IS NOT NULL)::integer = 1);
CREATE TABLE project_member (id uuid PRIMARY KEY,version bigint NOT NULL DEFAULT 0,project_id uuid NOT NULL REFERENCES technical_project(id),user_id uuid NOT NULL REFERENCES users(id),role varchar(16) NOT NULL CHECK(role IN ('OWNER','MANAGER','MEMBER','VIEWER')),function_name varchar(120),active boolean NOT NULL DEFAULT true,joined_at timestamptz NOT NULL DEFAULT now(),UNIQUE(project_id,user_id));
CREATE TABLE project_invitation (id uuid PRIMARY KEY,version bigint NOT NULL DEFAULT 0,project_id uuid NOT NULL REFERENCES technical_project(id),recipient_auth_id uuid,email varchar(254) NOT NULL,role varchar(16) NOT NULL CHECK(role IN ('MANAGER','MEMBER','VIEWER')),function_name varchar(120),status varchar(16) NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','ACCEPTED','DECLINED','REVOKED')),expires_at timestamptz NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),created_by uuid NOT NULL REFERENCES users(id),locale varchar(5) NOT NULL DEFAULT 'pt-BR',email_state varchar(16) NOT NULL DEFAULT 'PENDING',email_attempts integer NOT NULL DEFAULT 0,next_email_attempt_at timestamptz,responded_at timestamptz);
CREATE TABLE project_activity (id uuid PRIMARY KEY,version bigint NOT NULL DEFAULT 0,project_id uuid NOT NULL REFERENCES technical_project(id),title varchar(160) NOT NULL,description text,type varchar(16) NOT NULL CHECK(type IN ('SERVICE','VISIT','MEETING','OTHER')),status varchar(16) NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','IN_PROGRESS','COMPLETED','CANCELED')),starts_at timestamptz NOT NULL,ends_at timestamptz,onsite boolean NOT NULL DEFAULT false,assignee_ids uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],technical_service_id uuid REFERENCES technical_service(id),CHECK(ends_at IS NULL OR ends_at>starts_at));
CREATE TABLE project_history (id uuid PRIMARY KEY,version bigint NOT NULL DEFAULT 0,project_id uuid NOT NULL REFERENCES technical_project(id),actor_id uuid NOT NULL REFERENCES users(id),action varchar(40) NOT NULL,detail text NOT NULL,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE project_photo (id uuid PRIMARY KEY,version bigint NOT NULL DEFAULT 0,project_id uuid NOT NULL REFERENCES technical_project(id),name varchar(160) NOT NULL,mime varchar(40) NOT NULL CHECK(mime IN ('image/jpeg','image/png')),content bytea NOT NULL CHECK(octet_length(content)<=8388608),cover boolean NOT NULL DEFAULT false,uploaded_by uuid NOT NULL REFERENCES users(id),created_at timestamptz NOT NULL DEFAULT now());
CREATE UNIQUE INDEX uq_project_photo_cover ON project_photo(project_id) WHERE cover;
CREATE INDEX ix_project_company ON technical_project(owner_company_id,created_at DESC);
CREATE INDEX ix_project_personal ON technical_project(owner_user_id,created_at DESC);
CREATE INDEX ix_project_member_access ON project_member(user_id,project_id) WHERE active;
CREATE INDEX ix_project_invitation_recipient ON project_invitation(lower(email),status,expires_at);
CREATE INDEX ix_project_activity_agenda ON project_activity(project_id,starts_at);
CREATE INDEX ix_project_history_timeline ON project_history(project_id,created_at DESC);
CREATE INDEX ix_project_photo_gallery ON project_photo(project_id,created_at DESC);
-- New company permission is evaluated by ProjectAccess, while personal operations use project roles.
INSERT INTO permission(id,permission_name,name,description) VALUES(gen_random_uuid(),'POST /api/projects','Criar projetos','Criar projetos no contexto empresarial') ON CONFLICT(permission_name) DO NOTHING;

-- Existing service_status enum values are preserved; varchar matches the JPA string mapping.
ALTER TABLE technical_project ALTER COLUMN status DROP DEFAULT;
ALTER TABLE technical_project ALTER COLUMN status TYPE varchar(20) USING status::text;
ALTER TABLE technical_project ALTER COLUMN status SET DEFAULT 'OPEN';
ALTER TABLE technical_project ADD CONSTRAINT ck_project_status CHECK(status IN ('OPEN','IN_PROGRESS','COMPLETED','CANCELED'));
ALTER TABLE technical_service ALTER COLUMN status DROP DEFAULT;
ALTER TABLE technical_service ALTER COLUMN status TYPE varchar(20) USING status::text;
ALTER TABLE technical_service ALTER COLUMN status SET DEFAULT 'OPEN';
ALTER TABLE technical_service ADD CONSTRAINT ck_service_status CHECK(status IN ('OPEN','IN_PROGRESS','COMPLETED','CANCELED'));

UPDATE technical_project p SET location_state=a.state,location_city=left(a.city,120),
 location_neighborhood=left(a.neighborhood,120),location_zip_code=a.zip_code,
 location_street=left(a.street,180),location_number=a.number,location_complement=left(u.complement,180)
FROM local_unit u JOIN address a ON a.id=u.fk_address WHERE p.fk_local_unit=u.id;
INSERT INTO project_member(id,project_id,user_id,role,function_name)
SELECT gen_random_uuid(),s.fk_technical_project,person.fk_users,'MEMBER',left(min(e.function),120)
FROM service_executor e JOIN technical_service s ON s.id=e.fk_service
JOIN technician_affiliation affiliation ON affiliation.id=e.fk_technician_affiliation
JOIN technician technician ON technician.id=affiliation.fk_technician
JOIN person person ON person.id=technician.fk_person
WHERE person.fk_users IS NOT NULL GROUP BY s.fk_technical_project,person.fk_users
ON CONFLICT(project_id,user_id) DO NOTHING;

-- Approved independent professionals can execute work without a company affiliation.
ALTER TABLE technician_affiliation ALTER COLUMN fk_company DROP NOT NULL;
ALTER TABLE technician_affiliation ALTER COLUMN affiliation_type TYPE varchar(16) USING affiliation_type::text;
ALTER TABLE technician_affiliation ADD CONSTRAINT ck_affiliation_type CHECK(affiliation_type IN ('INDEPENDENT','AFFILIATED','PARTNER'));
ALTER TABLE technician_affiliation ADD CONSTRAINT ck_affiliation_company CHECK(fk_company IS NOT NULL OR affiliation_type='INDEPENDENT');
ALTER TABLE proposal ADD CONSTRAINT fk_proposal_supplier FOREIGN KEY (fk_supplier) REFERENCES supplier (id);
CREATE INDEX IF NOT EXISTS idx_proposal_supplier ON proposal (fk_supplier);
ALTER TABLE address ADD CONSTRAINT fk_address_owner_company FOREIGN KEY (fk_owner_company) REFERENCES company (id) DEFERRABLE INITIALLY DEFERRED;
CREATE UNIQUE INDEX uq_active_independent_affiliation ON technician_affiliation(fk_technician) WHERE active AND fk_company IS NULL AND affiliation_type='INDEPENDENT';

-- Preserve the technical-service history in the agenda without fabricating missing end times.
CREATE UNIQUE INDEX uq_project_activity_service ON project_activity(technical_service_id) WHERE technical_service_id IS NOT NULL;
INSERT INTO project_activity(id,project_id,title,type,status,starts_at,ends_at,assignee_ids,technical_service_id)
SELECT gen_random_uuid(),s.fk_technical_project,left(s.purpose,160),'SERVICE',s.status,
 coalesce(s.scheduled_date,s.created_at),
 CASE WHEN s.end_date>coalesce(s.scheduled_date,s.created_at) THEN s.end_date ELSE NULL END,
 coalesce((SELECT array_agg(DISTINCT person.fk_users) FROM service_executor e
 JOIN technician_affiliation a ON a.id=e.fk_technician_affiliation
 JOIN technician t ON t.id=a.fk_technician JOIN person person ON person.id=t.fk_person
 WHERE e.fk_service=s.id AND person.fk_users IS NOT NULL),ARRAY[]::uuid[]),s.id
FROM technical_service s;

-- company managed accounts (snapshot da migração V26).
-- A origem da conta é distinta dos vínculos de trabalho de um usuário independente.
ALTER TABLE users ADD COLUMN IF NOT EXISTS managed_by_company_id uuid REFERENCES company(id);
CREATE OR REPLACE FUNCTION enforce_managed_account_company() RETURNS trigger AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM users WHERE id = NEW.fk_users AND managed_by_company_id IS NOT NULL AND managed_by_company_id <> NEW.fk_company) THEN
    RAISE EXCEPTION 'Conta administrada pela empresa não pode ter vínculo com outra empresa' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER user_company_managed_account BEFORE INSERT OR UPDATE ON user_company FOR EACH ROW EXECUTE FUNCTION enforce_managed_account_company();

-- marketplace orders (snapshot da migração V27).
-- Carrinho e pedidos de compra de unidades de ofertas. Os pagamentos são fictícios: nenhum valor real é movimentado.
CREATE TABLE IF NOT EXISTS cart (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_users   uuid NOT NULL UNIQUE REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cart_item (
    id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_cart   uuid NOT NULL REFERENCES cart(id) ON DELETE CASCADE,
    fk_offer  uuid NOT NULL REFERENCES offer(id) ON DELETE CASCADE,
    quantity  integer NOT NULL CHECK (quantity > 0),
    added_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_cart_item_offer UNIQUE (fk_cart, fk_offer)
);

CREATE TABLE IF NOT EXISTS purchase_order (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_buyer       uuid NOT NULL REFERENCES users(id),
    status         varchar(16) NOT NULL DEFAULT 'PAID' CHECK (status IN ('PAID', 'CANCELED')),
    subtotal       numeric(12,2) NOT NULL CHECK (subtotal >= 0),
    fee_percentage numeric(6,5) NOT NULL CHECK (fee_percentage >= 0 AND fee_percentage <= 1),
    fee_amount     numeric(12,2) NOT NULL CHECK (fee_amount >= 0),
    total          numeric(12,2) NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    canceled_at    timestamptz,
    canceled_by    uuid REFERENCES users(id),
    CONSTRAINT ck_purchase_order_total CHECK (total = subtotal + fee_amount),
    CONSTRAINT ck_purchase_order_canceled CHECK ((status = 'CANCELED') = (canceled_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS order_item (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_order            uuid NOT NULL REFERENCES purchase_order(id) ON DELETE CASCADE,
    fk_offer            uuid REFERENCES offer(id) ON DELETE SET NULL,
    fk_supplier         uuid NOT NULL REFERENCES supplier(id),
    offer_slug          varchar(160) NOT NULL,
    model_name          varchar(255) NOT NULL,
    unit_price          numeric(12,2) NOT NULL CHECK (unit_price >= 0),
    discount_percentage numeric(5,2) NOT NULL DEFAULT 0 CHECK (discount_percentage >= 0 AND discount_percentage <= 100),
    net_unit_price      numeric(12,2) NOT NULL,
    quantity            integer NOT NULL CHECK (quantity > 0),
    line_total          numeric(12,2) NOT NULL,
    CONSTRAINT ck_order_item_net_price CHECK (net_unit_price = round(unit_price * (100 - discount_percentage) / 100, 2)),
    CONSTRAINT ck_order_item_line_total CHECK (line_total = net_unit_price * quantity)
);

CREATE TABLE IF NOT EXISTS order_payment (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_order    uuid NOT NULL UNIQUE REFERENCES purchase_order(id) ON DELETE CASCADE,
    method      payment_method NOT NULL,
    amount      numeric(12,2) NOT NULL CHECK (amount >= 0),
    status      varchar(16) NOT NULL DEFAULT 'PAID' CHECK (status IN ('PAID', 'REFUNDED')),
    paid_at     timestamptz NOT NULL DEFAULT now(),
    refunded_at timestamptz,
    CONSTRAINT ck_order_payment_refunded CHECK ((status = 'REFUNDED') = (refunded_at IS NOT NULL))
);

-- Usuário de empresa fornecedora não compra, salvo se for profissional registrado e aprovado. Ninguém compra de uma
-- empresa fornecedora à qual pertence.
CREATE OR REPLACE FUNCTION enforce_order_buyer_eligibility() RETURNS trigger AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM user_company uc JOIN supplier s ON s.fk_company = uc.fk_company WHERE uc.fk_users = NEW.fk_buyer)
     AND NOT EXISTS (SELECT 1 FROM person p JOIN technician t ON t.fk_person = p.id WHERE p.fk_users = NEW.fk_buyer AND t.status = 'APPROVED') THEN
    RAISE EXCEPTION 'Usuário de empresa fornecedora não pode comprar' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS purchase_order_buyer_not_supplier ON purchase_order;
DROP TRIGGER IF EXISTS purchase_order_buyer_eligibility ON purchase_order;
CREATE TRIGGER purchase_order_buyer_eligibility BEFORE INSERT ON purchase_order FOR EACH ROW EXECUTE FUNCTION enforce_order_buyer_eligibility();

CREATE OR REPLACE FUNCTION enforce_order_item_not_own_supplier() RETURNS trigger AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM purchase_order o JOIN user_company uc ON uc.fk_users = o.fk_buyer JOIN supplier s ON s.fk_company = uc.fk_company
             WHERE o.id = NEW.fk_order AND s.id = NEW.fk_supplier) THEN
    RAISE EXCEPTION 'Não é possível comprar de uma empresa à qual o comprador pertence' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS order_item_not_own_supplier ON order_item;
CREATE TRIGGER order_item_not_own_supplier BEFORE INSERT ON order_item FOR EACH ROW EXECUTE FUNCTION enforce_order_item_not_own_supplier();

CREATE INDEX IF NOT EXISTS idx_purchase_order_buyer ON purchase_order (fk_buyer, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_order_item_order ON order_item (fk_order);
CREATE INDEX IF NOT EXISTS idx_order_item_supplier ON order_item (fk_supplier, fk_order);
CREATE INDEX IF NOT EXISTS idx_order_item_offer ON order_item (fk_offer) WHERE fk_offer IS NOT NULL;

-- purchase permissions (snapshot da migração V28).
INSERT INTO permission (id, permission_name, name, description)
SELECT gen_random_uuid(), v.permission_name, v.name, v.description
FROM (VALUES
    ('GET /api/cart', 'Ver carrinho', 'Consultar os itens do próprio carrinho'),
    ('PUT /api/cart/items/{offerId}', 'Alterar carrinho', 'Adicionar uma oferta ou mudar a quantidade no carrinho'),
    ('DELETE /api/cart/items/{offerId}', 'Remover item do carrinho', 'Tirar uma oferta do carrinho'),
    ('POST /api/orders', 'Comprar', 'Finalizar a compra dos itens do carrinho'),
    ('GET /api/orders', 'Ver pedidos', 'Consultar os próprios pedidos'),
    ('GET /api/orders/{id}', 'Ver pedido', 'Consultar o detalhe e o comprovante de um pedido próprio'),
    ('PATCH /api/orders/{id}/cancel', 'Cancelar pedido', 'Cancelar um pedido próprio e devolver o estoque'),
    ('GET /api/sales', 'Ver vendas', 'Consultar os itens vendidos pela empresa fornecedora'),
    ('GET /api/subscription', 'Ver plano da empresa', 'Consultar plano, status e cobranças da empresa fornecedora'),
    ('POST /api/charges/{id}/payment', 'Pagar cobrança do plano', 'Pagar, de forma simulada, uma cobrança pendente do plano')
) AS v(permission_name, name, description)
WHERE NOT EXISTS (SELECT 1 FROM permission p WHERE p.permission_name = v.permission_name);
