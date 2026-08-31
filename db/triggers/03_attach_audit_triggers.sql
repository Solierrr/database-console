-- Aplica a auditoria nas tabelas mais criticas do dominio de negocio.

CREATE TRIGGER trg_audit_company
AFTER INSERT OR UPDATE OR DELETE ON company
FOR EACH ROW EXECUTE FUNCTION fn_audit_trigger();

CREATE TRIGGER trg_audit_proposal
AFTER INSERT OR UPDATE OR DELETE ON proposal
FOR EACH ROW EXECUTE FUNCTION fn_audit_trigger();

CREATE TRIGGER trg_audit_technical_service
AFTER INSERT OR UPDATE OR DELETE ON technical_service
FOR EACH ROW EXECUTE FUNCTION fn_audit_trigger();
