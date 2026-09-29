-- Plano padrão gratuito, usado pra assinar automaticamente todo fornecedor
-- novo (pré-requisito técnico pra criar ofertas — ver OfferService.save,
-- que exige assinatura ativa via SubscriptionService.isSupplierSubscriptionActive).
INSERT INTO company_plans (id, name, value, cycle)
SELECT gen_random_uuid(), 'Gratuito', 0, 'MONTHLY'
WHERE NOT EXISTS (SELECT 1 FROM company_plans WHERE name = 'Gratuito');
