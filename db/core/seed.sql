-- =============================================================================
-- db/core/seed.sql
--
-- Massa de dados minima para desenvolvimento local do api-core: uma empresa
-- fornecedora com um modelo/oferta em catalogo, e uma empresa solicitante com
-- uma unidade e uma proposta. NAO usar em staging/producao.
--
-- Os UUIDs de users.auth_id abaixo sao os MESMOS usados em db/auth/seed.sql,
-- para que os dois bancos fiquem coerentes entre si num ambiente local.
--
-- Rode apos enums.sql + schema.sql (+ indexes.sql, opcional para seed).
-- =============================================================================

-- Usuarios de plataforma, ligados aos auth_user do banco do api-auth.
INSERT INTO users (id, auth_id, username, active)
VALUES ('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 'requester_demo', true);

INSERT INTO users (id, auth_id, username, active)
VALUES ('44444444-4444-4444-4444-444444444444', '22222222-2222-2222-2222-222222222222', 'supplier_demo', true);

-- Empresa fornecedora.
INSERT INTO address (id, state, city, zip_code, street, number)
VALUES ('55555555-5555-5555-5555-555555555555', 'SP', 'Sao Paulo', '01001000', 'Praca da Se', '100');

INSERT INTO business_contact (id, company_email, phone)
VALUES ('66666666-6666-6666-6666-666666666666', 'contato@fornecedor-demo.dev', '11999990000');

INSERT INTO company (id, status, fk_address, fk_business_contact, cnpj, trade_name, corporate_name)
VALUES (
    '77777777-7777-7777-7777-777777777777',
    'APPROVED',
    '55555555-5555-5555-5555-555555555555',
    '66666666-6666-6666-6666-666666666666',
    '00000000000191',
    'Fornecedor Demo',
    'Fornecedor Demo Solar Ltda'
);

INSERT INTO supplier (id, fk_company, status, business_type)
VALUES ('88888888-8888-8888-8888-888888888888', '77777777-7777-7777-7777-777777777777', 'ACTIVE', 'DISTRIBUIDOR');

-- Catalogo: um modelo de painel homologado e uma oferta do fornecedor demo.
INSERT INTO model (id, brand, model, power_wp, efficiency, dimension, weight, status)
VALUES (
    '99999999-9999-9999-9999-999999999999',
    'SolarTech',
    'ST-450W',
    450,
    21.5,
    2.1,
    23.5,
    'APPROVED'
);

INSERT INTO offer (id, fk_supplier, fk_model, unit_price, availability)
VALUES (
    'aaaaaaaa-1111-1111-1111-111111111111',
    '88888888-8888-8888-8888-888888888888',
    '99999999-9999-9999-9999-999999999999',
    899.90,
    100
);

-- Empresa solicitante, com uma unidade de instalacao.
INSERT INTO company (id, status, cnpj, trade_name, corporate_name)
VALUES (
    'bbbbbbbb-1111-1111-1111-111111111111',
    'APPROVED',
    '11111111000191',
    'Requester Demo',
    'Requester Demo Energia Ltda'
);

INSERT INTO requester (id, fk_company, business_type)
VALUES ('cccccccc-1111-1111-1111-111111111111', 'bbbbbbbb-1111-1111-1111-111111111111', 'RESIDENCIAL');

INSERT INTO address (id, state, city, zip_code, street, number)
VALUES ('dddddddd-1111-1111-1111-111111111111', 'SP', 'Campinas', '13010000', 'Rua das Flores', '250');

INSERT INTO local_unit (id, fk_requester, fk_address, location_type)
VALUES (
    'eeeeeeee-1111-1111-1111-111111111111',
    'cccccccc-1111-1111-1111-111111111111',
    'dddddddd-1111-1111-1111-111111111111',
    'HOUSE'
);

-- Proposta em negociacao, com um item vindo da oferta do fornecedor demo.
INSERT INTO proposal (id, fk_requester, status, notes)
VALUES (
    'ffffffff-1111-1111-1111-111111111111',
    'cccccccc-1111-1111-1111-111111111111',
    'AWAITING_SUPPLIER',
    'Proposta de seed para desenvolvimento local.'
);

INSERT INTO proposal_item (id, fk_proposal, fk_offer, quantity)
VALUES (
    '11111111-2222-2222-2222-222222222222',
    'ffffffff-1111-1111-1111-111111111111',
    'aaaaaaaa-1111-1111-1111-111111111111',
    10
);

INSERT INTO proposal_unit (fk_proposal_item, fk_local_unit, quantity)
VALUES ('11111111-2222-2222-2222-222222222222', 'eeeeeeee-1111-1111-1111-111111111111', 10);
