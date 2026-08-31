-- Popula/atualiza data_catalog a partir do information_schema (nome e
-- tipo de cada coluna do schema public), preservando business_rule e
-- access_level ja anotados manualmente para colunas existentes.

CREATE OR REPLACE PROCEDURE sp_refresh_data_catalog()
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO data_catalog (table_name, column_name, data_type)
    SELECT c.table_name, c.column_name, c.data_type
    FROM information_schema.columns c
    JOIN information_schema.tables t
        ON t.table_schema = c.table_schema AND t.table_name = c.table_name
    WHERE c.table_schema = 'public'
      AND t.table_type = 'BASE TABLE'
    ON CONFLICT (table_name, column_name)
    DO UPDATE SET data_type = EXCLUDED.data_type, updated_at = now();
END;
$$;
