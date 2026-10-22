DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM inventory GROUP BY fk_supplier, fk_model HAVING count(*) > 1) THEN
        RAISE EXCEPTION 'Duplicate inventory supplier/model pairs; reconcile verified records before V13';
    END IF;
END $$;

ALTER TABLE inventory ADD CONSTRAINT uq_inventory_supplier_model UNIQUE (fk_supplier, fk_model);
ALTER TABLE offer ADD CONSTRAINT ck_offer_unit_price CHECK (unit_price > 0);
ALTER TABLE offer ADD CONSTRAINT ck_offer_discount CHECK (discount_percentage BETWEEN 0 AND 100);
ALTER TABLE offer ADD CONSTRAINT ck_offer_translation_status CHECK (translation_status IN ('PENDING', 'COMPLETED', 'FAILED'));
ALTER TABLE professional_document ADD CONSTRAINT ck_professional_document_storage CHECK (
    (content IS NOT NULL AND octet_length(content) > 0 AND cloudinary_public_id IS NULL AND cloudinary_format IS NULL)
    OR (content IS NULL AND cloudinary_public_id IS NOT NULL AND length(trim(cloudinary_public_id)) > 0
        AND cloudinary_format IS NOT NULL AND length(trim(cloudinary_format)) > 0)
);
ALTER TABLE professional_submission ADD CONSTRAINT ck_professional_submission_status
    CHECK (status IN ('QUEUED', 'VALIDATING', 'RETRY_PENDING', 'MANUAL_REVIEW', 'APPROVED', 'REJECTED', 'SUSPENDED', 'REINSTATED'));
ALTER TABLE professional_submission ADD CONSTRAINT ck_professional_submission_attempts CHECK (attempts >= 0);

