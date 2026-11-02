-- Catálogo de dados (governança): uma linha por coluna, com tipo, descrição, regra de negócio
-- e nível de acesso. Os campos técnicos são recarregados de information_schema; a descrição vem
-- de COMMENT ON COLUMN, e a regra de negócio e o nível de acesso podem ser editados à mão sem
-- que a recarga os sobrescreva.

CREATE SCHEMA IF NOT EXISTS governance;

CREATE TABLE IF NOT EXISTS governance.data_catalog (
    schema_name text NOT NULL,
    table_name text NOT NULL,
    column_name text NOT NULL,
    data_type text NOT NULL,
    is_nullable boolean NOT NULL,
    description text,
    business_rule text,
    access_level text NOT NULL DEFAULT 'interno'
        CHECK (access_level IN ('publico', 'interno', 'restrito', 'sensivel')),
    refreshed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (schema_name, table_name, column_name)
);

COMMENT ON TABLE governance.data_catalog IS 'Catálogo técnico de metadados: tabelas, colunas, regras de negócio e níveis de acesso.';
COMMENT ON COLUMN governance.data_catalog.access_level IS 'publico, interno, restrito (só leitura analítica) ou sensivel (dado pessoal, LGPD).';

-- Regra de negócio e nível de acesso padrão por tabela.
CREATE TABLE IF NOT EXISTS governance.table_rule (
    table_name text PRIMARY KEY,
    business_rule text NOT NULL,
    access_level text NOT NULL CHECK (access_level IN ('publico', 'interno', 'restrito', 'sensivel'))
);

INSERT INTO governance.table_rule (table_name, business_rule, access_level) VALUES
    ('company', 'Empresa da plataforma. O tipo define se ela vira fornecedora (SUPPLIER) ou demandante (REQUESTER).', 'interno'),
    ('supplier', 'Fornecedor ligado a uma empresa; oferece painéis e assina um plano.', 'interno'),
    ('requester', 'Demandante ligado a uma empresa; pede propostas e compra.', 'interno'),
    ('model', 'Modelo de painel solar de uma marca, com potência, eficiência e dimensões.', 'publico'),
    ('brand', 'Marca de painéis; o catálogo de modelos referencia a marca.', 'publico'),
    ('offer', 'Oferta de um fornecedor para um modelo. Preço unitário maior que zero, desconto de 0 a 100% e disponibilidade não negativa.', 'publico'),
    ('proposal', 'Negociação entre demandante e fornecedor. Situações: AWAITING_SUPPLIER, AWAITING_REQUESTER, ACCEPTED, REJECTED e CANCELED.', 'interno'),
    ('proposal_item', 'Item de uma proposta. Valor = preço negociado × quantidade, sem aplicar o desconto uma segunda vez.', 'interno'),
    ('purchase_order', 'Pedido de compra. CANCELED exige canceled_at; o comprador precisa ser elegível e não pode comprar do próprio fornecedor.', 'interno'),
    ('order_item', 'Item de pedido com o preço e o nome do modelo congelados no momento da compra.', 'interno'),
    ('subscription', 'Assinatura de um fornecedor a um plano.', 'interno'),
    ('charge', 'Cobrança de uma assinatura, gerada pela procedure generate_subscription_charge com o valor do plano.', 'restrito'),
    ('user_account', 'Perfil do usuário na plataforma; liga a identidade do api-auth pelo campo auth_id.', 'interno'),
    ('person', 'Dados pessoais de quem usa a plataforma.', 'sensivel'),
    ('contact', 'E-mail e telefone de contato.', 'sensivel'),
    ('address', 'Endereço de empresa ou unidade.', 'sensivel'),
    ('local_unit', 'Unidade (local de instalação) de um demandante.', 'interno')
ON CONFLICT (table_name) DO UPDATE
SET business_rule = EXCLUDED.business_rule,
    access_level = EXCLUDED.access_level;

-- Recarrega as colunas existentes e remove as que não existem mais. Mantém o que foi editado à mão.
CREATE OR REPLACE PROCEDURE governance.refresh_data_catalog()
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO governance.data_catalog
        (schema_name, table_name, column_name, data_type, is_nullable, description, business_rule, access_level)
    SELECT c.table_schema,
           c.table_name,
           c.column_name,
           c.data_type,
           (c.is_nullable = 'YES'),
           col_description(format('%I.%I', c.table_schema, c.table_name)::regclass, c.ordinal_position::int),
           r.business_rule,
           CASE
               WHEN c.column_name ~* '(cpf|cnpj|email|phone|birth|password|token|ip_address|zip_code|street)' THEN 'sensivel'
               WHEN c.table_schema <> 'public' THEN 'restrito'
               ELSE COALESCE(r.access_level, 'interno')
           END
    FROM information_schema.columns c
    JOIN information_schema.tables t
      ON t.table_schema = c.table_schema AND t.table_name = c.table_name
    LEFT JOIN governance.table_rule r
      ON r.table_name = c.table_name AND c.table_schema = 'public'
    WHERE t.table_type IN ('BASE TABLE', 'VIEW')
      AND c.table_schema IN ('public', 'export', 'bi')
      AND c.table_name <> 'flyway_schema_history'
    ON CONFLICT (schema_name, table_name, column_name) DO UPDATE
    SET data_type = EXCLUDED.data_type,
        is_nullable = EXCLUDED.is_nullable,
        description = COALESCE(EXCLUDED.description, governance.data_catalog.description),
        refreshed_at = now();

    DELETE FROM governance.data_catalog d
    WHERE NOT EXISTS (
        SELECT 1
        FROM information_schema.columns c
        WHERE c.table_schema = d.schema_name
          AND c.table_name = d.table_name
          AND c.column_name = d.column_name
    );
END;
$$;

CALL governance.refresh_data_catalog();
