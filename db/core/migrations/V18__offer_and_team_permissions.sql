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
