-- O api-core escopa enderecos pela empresa dona (Address.ownerCompany) e propostas pelo fornecedor (Proposal.supplier);
-- essas colunas nao existiam no schema.
ALTER TABLE address ADD COLUMN IF NOT EXISTS fk_owner_company UUID;

UPDATE address a SET fk_owner_company = c.id
FROM company c
WHERE c.fk_address = a.id AND a.fk_owner_company IS NULL;

UPDATE address a SET fk_owner_company = r.fk_company
FROM local_unit u
JOIN requester r ON r.id = u.fk_requester
WHERE u.fk_address = a.id AND a.fk_owner_company IS NULL;

ALTER TABLE address
    ADD CONSTRAINT fk_address_owner_company FOREIGN KEY (fk_owner_company) REFERENCES company (id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX IF NOT EXISTS idx_address_owner_company ON address (fk_owner_company);

ALTER TABLE proposal ADD COLUMN IF NOT EXISTS fk_supplier UUID;

UPDATE proposal p SET fk_supplier = o.fk_supplier
FROM (SELECT DISTINCT ON (pi.fk_proposal) pi.fk_proposal, off.fk_supplier
      FROM proposal_item pi JOIN offer off ON off.id = pi.fk_offer
      ORDER BY pi.fk_proposal, pi.id) o
WHERE o.fk_proposal = p.id AND p.fk_supplier IS NULL;

ALTER TABLE proposal ADD CONSTRAINT fk_proposal_supplier FOREIGN KEY (fk_supplier) REFERENCES supplier (id);
ALTER TABLE proposal ALTER COLUMN notes TYPE VARCHAR(500);
CREATE INDEX IF NOT EXISTS idx_proposal_supplier ON proposal (fk_supplier);

-- Colunas legadas que as entidades atuais nao preenchem mais (as permissoes ficam em position_permission e
-- a certificacao deixou de pertencer a um tecnico): sem isto os inserts do api-core violam NOT NULL.
ALTER TABLE position ALTER COLUMN accesses DROP NOT NULL;
ALTER TABLE certification ALTER COLUMN fk_technician DROP NOT NULL;
ALTER TABLE certification ALTER COLUMN type DROP NOT NULL;
ALTER TABLE certification ALTER COLUMN information DROP NOT NULL;
