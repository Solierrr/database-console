-- Permite que funcionários com "Ver funcionários" também consigam ver o nome
-- de outros usuários da empresa (necessário pra listar funcionários por nome).
INSERT INTO permission (id, permission_name, name, description)
SELECT gen_random_uuid(), 'GET /api/users/{id}', 'Ver usuários', 'Consultar dados básicos de outro usuário'
WHERE NOT EXISTS (SELECT 1 FROM permission WHERE permission_name = 'GET /api/users/{id}');
