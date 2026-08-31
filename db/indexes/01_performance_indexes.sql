-- Indices de otimizacao para os predicados/joins mais frequentes do
-- dominio (proposta, oferta, eventos de seguranca) e para os filtros de
-- status usados nas views de BI e no monitoramento.
-- Justificativa/medicao de cada indice: ver docs/query_optimization.md.

CREATE INDEX idx_proposal_item_fk_proposal ON proposal_item (fk_proposal);
CREATE INDEX idx_proposal_status ON proposal (status);
CREATE INDEX idx_proposal_created_at ON proposal (created_at);

CREATE INDEX idx_offer_fk_supplier ON offer (fk_supplier);
CREATE INDEX idx_offer_fk_model ON offer (fk_model);

CREATE INDEX idx_security_event_fk_user_occurred_at ON security_event (fk_user, occurred_at DESC);
CREATE INDEX idx_technical_service_status ON technical_service (status);
CREATE INDEX idx_technical_service_fk_project ON technical_service (fk_technical_project);

CREATE INDEX idx_access_log_accessed_at ON access_log (accessed_at);
CREATE INDEX idx_audit_log_table_performed_at ON audit_log (table_name, performed_at DESC);

CREATE INDEX idx_professional_review_fk_professional ON professional_review (fk_professional);
CREATE INDEX idx_refresh_token_fk_replaced_by ON refresh_token (fk_replaced_by);
