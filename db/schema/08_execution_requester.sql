-- Dominio de execucao, parte 1 (espelha api-core.execution.Requester).
-- Separado do restante de "execution" porque unit.local_unit depende de
-- requester, e technical_project depende de unit.local_unit -- para
-- resolver a dependencia circular entre os dois dominios, requester
-- nasce primeiro e o restante de execution vem depois de 09_unit.sql.

CREATE TABLE requester (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_company UUID NOT NULL REFERENCES company (id)
);
