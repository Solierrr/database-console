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
