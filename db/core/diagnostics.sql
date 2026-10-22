SELECT fk_supplier, fk_model, count(*) FROM inventory GROUP BY fk_supplier, fk_model HAVING count(*) > 1;
SELECT id FROM offer WHERE unit_price <= 0 OR discount_percentage < 0 OR discount_percentage > 100
    OR translation_status NOT IN ('PENDING', 'COMPLETED', 'FAILED');
SELECT id FROM professional_document WHERE NOT (
    (content IS NOT NULL AND octet_length(content) > 0 AND cloudinary_public_id IS NULL AND cloudinary_format IS NULL)
    OR (content IS NULL AND cloudinary_public_id IS NOT NULL AND length(trim(cloudinary_public_id)) > 0
        AND cloudinary_format IS NOT NULL AND length(trim(cloudinary_format)) > 0)
);
