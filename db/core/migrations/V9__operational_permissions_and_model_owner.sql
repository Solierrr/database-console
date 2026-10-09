ALTER TABLE model ADD COLUMN IF NOT EXISTS fk_creator_company UUID REFERENCES company(id);

INSERT INTO permission (id, permission_name, name, description)
SELECT gen_random_uuid(), v.permission_name, v.name, v.description
FROM (VALUES
    ('GET /api/models', 'Ver modelos', 'Consultar o catálogo compartilhado de modelos'),
    ('DELETE /api/models/{id}', 'Remover modelos', 'Remover modelos próprios em análise'),
    ('DELETE /api/local-units/{id}', 'Remover unidades', 'Remover unidades da empresa'),
    ('DELETE /api/access-codes/{id}/company/{companyId}', 'Revogar códigos', 'Revogar códigos de acesso da empresa'),
    ('POST /api/positions', 'Criar cargos', 'Criar cargos para a empresa'),
    ('POST /api/company-positions', 'Vincular cargos', 'Disponibilizar cargos para a empresa'),
    ('GET /api/company-positions/company/{companyId}', 'Ver cargos', 'Listar cargos da empresa'),
    ('GET /api/permissions', 'Ver permissões disponíveis', 'Consultar o catálogo de permissões'),
    ('GET /api/position-permissions/position/{positionId}', 'Ver permissões de cargos', 'Consultar as permissões de cargos da empresa'),
    ('POST /api/position-permissions', 'Conceder permissões', 'Conceder permissões a cargos próprios'),
    ('DELETE /api/position-permissions/{id}', 'Revogar permissões', 'Revogar permissões de cargos próprios'),
    ('POST /auth/password/change', 'Alterar própria senha', 'Permitir alteração de senha de identidade empresarial'),
    ('POST /auth/password/recovery', 'Recuperar própria senha', 'Permitir recuperação de senha de identidade empresarial')
) AS v(permission_name, name, description)
WHERE NOT EXISTS (SELECT 1 FROM permission p WHERE p.permission_name = v.permission_name);
