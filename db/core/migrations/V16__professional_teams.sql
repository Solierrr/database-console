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
