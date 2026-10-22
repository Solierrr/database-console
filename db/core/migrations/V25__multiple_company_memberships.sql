-- Um usuário pode operar em várias empresas; o vínculo não se repete na mesma empresa.
DROP INDEX IF EXISTS idx_user_company_user_unique;
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_company_company_user_unique ON user_company (fk_company, fk_users);
CREATE INDEX IF NOT EXISTS idx_user_company_user ON user_company (fk_users);
