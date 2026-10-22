-- =============================================================================
-- db/core/indexes.sql
--
-- Indices de otimizacao do banco do api-core, alem dos indices implicitos
-- criados pelas PKs/UNIQUEs em schema.sql.
--
-- Nenhuma @Entity do api-core declara @Index -- o Postgres NAO cria indice
-- automatico em coluna de FK (diferente da PK). Os indices abaixo cobrem os
-- padroes de consulta mais obvios do dominio (listar por empresa, por
-- fornecedor, por proposta, trilha de auditoria por usuario) e sao uma
-- recomendacao deste repositorio -- ainda nao existem em producao. Rode
-- apos schema.sql.
-- =============================================================================

-- Empresas de um usuario / usuarios de uma empresa.
CREATE INDEX IF NOT EXISTS idx_user_company_company ON user_company (fk_company);

-- Fornecedores e solicitantes por empresa.
CREATE INDEX IF NOT EXISTS idx_supplier_company ON supplier (fk_company);
CREATE INDEX IF NOT EXISTS idx_requester_company ON requester (fk_company);

-- Catalogo: ofertas e estoque por fornecedor/modelo.
CREATE INDEX IF NOT EXISTS idx_offer_supplier ON offer (fk_supplier);
CREATE INDEX IF NOT EXISTS idx_offer_model ON offer (fk_model);

-- Assinatura e cobranca por fornecedor.
CREATE INDEX IF NOT EXISTS idx_subscription_supplier ON subscription (fk_supplier);
CREATE INDEX IF NOT EXISTS idx_charge_subscription ON charge (fk_subscription);

-- Unidades e projetos por requester.
CREATE INDEX IF NOT EXISTS idx_local_unit_requester ON local_unit (fk_requester);
CREATE INDEX IF NOT EXISTS idx_technical_project_requester ON technical_project (fk_requester);

-- Propostas: listar por requester, itens por proposta, itens por oferta.
CREATE INDEX IF NOT EXISTS idx_proposal_requester ON proposal (fk_requester);
CREATE INDEX IF NOT EXISTS idx_proposal_item_proposal ON proposal_item (fk_proposal);
CREATE INDEX IF NOT EXISTS idx_proposal_item_offer ON proposal_item (fk_offer);

-- Execucao de servico: servicos por projeto, executores por servico.
CREATE INDEX IF NOT EXISTS idx_technical_service_project ON technical_service (fk_technical_project);
CREATE INDEX IF NOT EXISTS idx_service_executor_service ON service_executor (fk_service);

-- Qualificacao profissional por tecnico.
CREATE INDEX IF NOT EXISTS idx_technician_person ON technician (fk_person);
CREATE INDEX IF NOT EXISTS idx_professional_registration_technician ON professional_registration (fk_technician);
CREATE INDEX IF NOT EXISTS idx_technician_affiliation_technician ON technician_affiliation (fk_technician);
CREATE INDEX IF NOT EXISTS idx_shift_technician ON shift (fk_technician);

-- Avaliacoes recebidas por um tecnico, mais recentes primeiro.
CREATE INDEX IF NOT EXISTS idx_professional_review_professional ON professional_review (fk_professional, created_at DESC);

-- Trilha de auditoria por usuario, mais recente primeiro.
CREATE INDEX IF NOT EXISTS idx_flux_log_user ON flux_log (fk_user, created_at DESC);

-- Pedidos de compra.
CREATE INDEX IF NOT EXISTS idx_purchase_order_buyer ON purchase_order (fk_buyer, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_order_item_order ON order_item (fk_order);
CREATE INDEX IF NOT EXISTS idx_order_item_supplier ON order_item (fk_supplier, fk_order);
CREATE INDEX IF NOT EXISTS idx_order_item_offer ON order_item (fk_offer) WHERE fk_offer IS NOT NULL;
