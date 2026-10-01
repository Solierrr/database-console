INSERT INTO permission (id, permission_name, name, description)
SELECT gen_random_uuid(), v.permission_name, v.name, v.description
FROM (VALUES
    ('GET /api/suppliers/company/{companyId}', 'Ver dados de fornecedor', 'Consultar dados da empresa fornecedora'),
    ('GET /api/requesters/company/{companyId}', 'Ver dados de demandante', 'Consultar dados da empresa demandante'),
    ('GET /api/models/status/{status}', 'Ver modelos por situação', 'Consultar modelos por situação de análise'),
    ('POST /api/geolocalizations', 'Cadastrar localização', 'Salvar localização de uma unidade')
) AS v(permission_name, name, description)
WHERE NOT EXISTS (SELECT 1 FROM permission p WHERE p.permission_name = v.permission_name);
