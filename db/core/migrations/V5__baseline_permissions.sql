-- Catálogo base de permissões pra Gerências (fase 05 do plano de telas web).
-- `permission_name` precisa bater exatamente com o "METODO /caminho" usado por
-- EndpointAuthorizationInterceptor (ver RbacAuthorizationService.positionHasPermission).
INSERT INTO permission (id, permission_name, name, description)
SELECT gen_random_uuid(), v.permission_name, v.name, v.description
FROM (VALUES
    ('POST /api/offers', 'Criar ofertas', 'Cadastrar novas ofertas de placas solares'),
    ('PUT /api/offers/{id}', 'Editar ofertas', 'Atualizar ofertas já cadastradas'),
    ('DELETE /api/offers/{id}', 'Remover ofertas', 'Excluir ofertas cadastradas'),
    ('GET /api/offers/company/{companyId}', 'Ver ofertas', 'Listar as ofertas da empresa'),
    ('POST /api/models', 'Criar placas solares', 'Cadastrar novos modelos de placa solar'),
    ('PUT /api/models/{id}', 'Editar placas solares', 'Atualizar modelos de placa solar já cadastrados'),
    ('POST /api/access-codes', 'Convidar funcionários', 'Gerar código de acesso para novos funcionários'),
    ('GET /api/access-codes/company/{companyId}', 'Ver códigos de acesso', 'Listar códigos de acesso gerados pela empresa'),
    ('PATCH /api/user-companies/{id}/position', 'Editar cargo de funcionários', 'Alterar o cargo de um funcionário'),
    ('DELETE /api/user-companies/{id}', 'Remover funcionários', 'Desligar um funcionário da empresa'),
    ('GET /api/user-companies/company/{companyId}', 'Ver funcionários', 'Listar os funcionários da empresa'),
    ('POST /api/local-units', 'Criar unidades', 'Cadastrar novas unidades locais'),
    ('PUT /api/local-units/{id}', 'Editar unidades', 'Atualizar unidades locais já cadastradas'),
    ('GET /api/local-units/company/{companyId}', 'Ver unidades', 'Listar as unidades da empresa')
) AS v(permission_name, name, description)
WHERE NOT EXISTS (SELECT 1 FROM permission p WHERE p.permission_name = v.permission_name);
