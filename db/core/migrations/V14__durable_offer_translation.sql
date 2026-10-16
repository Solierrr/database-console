CREATE TABLE offer_translation_job (
    id UUID PRIMARY KEY,
    offer_id UUID NOT NULL REFERENCES offer(id) ON DELETE CASCADE,
    source_translation_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED',
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    claim_token UUID,
    error_code VARCHAR(40),
    CONSTRAINT uq_offer_translation_job_source UNIQUE (offer_id, source_translation_id),
    CONSTRAINT ck_offer_translation_job_status CHECK (status IN ('QUEUED','PROCESSING','RETRY_PENDING','COMPLETED','FAILED','CANCELLED')),
    CONSTRAINT ck_offer_translation_job_attempts CHECK (attempts >= 0)
);
CREATE INDEX idx_offer_translation_job_available ON offer_translation_job (available_at, id)
    WHERE status IN ('QUEUED', 'PROCESSING', 'RETRY_PENDING');
INSERT INTO offer_translation_job(id,offer_id,source_translation_id)
SELECT gen_random_uuid(), o.id, t.id FROM offer o JOIN offer_translation t ON t.fk_offer=o.id
WHERE t.locale='und' AND o.translation_status IN ('PENDING','FAILED');
