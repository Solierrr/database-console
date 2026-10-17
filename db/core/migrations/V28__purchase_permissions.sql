INSERT INTO permission (id, permission_name, name, description)
SELECT gen_random_uuid(), v.permission_name, v.name, v.description
FROM (VALUES
    ('GET /api/cart', 'Ver carrinho', 'Consultar os itens do próprio carrinho'),
    ('PUT /api/cart/items/{offerId}', 'Alterar carrinho', 'Adicionar uma oferta ou mudar a quantidade no carrinho'),
    ('DELETE /api/cart/items/{offerId}', 'Remover item do carrinho', 'Tirar uma oferta do carrinho'),
    ('POST /api/orders', 'Comprar', 'Finalizar a compra dos itens do carrinho'),
    ('GET /api/orders', 'Ver pedidos', 'Consultar os próprios pedidos'),
    ('GET /api/orders/{id}', 'Ver pedido', 'Consultar o detalhe e o comprovante de um pedido próprio'),
    ('PATCH /api/orders/{id}/cancel', 'Cancelar pedido', 'Cancelar um pedido próprio e devolver o estoque'),
    ('GET /api/sales', 'Ver vendas', 'Consultar os itens vendidos pela empresa fornecedora'),
    ('GET /api/subscription', 'Ver plano da empresa', 'Consultar plano, status e cobranças da empresa fornecedora'),
    ('POST /api/charges/{id}/payment', 'Pagar cobrança do plano', 'Pagar, de forma simulada, uma cobrança pendente do plano')
) AS v(permission_name, name, description)
WHERE NOT EXISTS (SELECT 1 FROM permission p WHERE p.permission_name = v.permission_name);
