CREATE TABLE IF NOT EXISTS professional_onboarding (
    id UUID PRIMARY KEY, auth_id UUID NOT NULL UNIQUE, user_id UUID NOT NULL REFERENCES users(id),
    technician_id UUID REFERENCES technician(id), revision BIGINT NOT NULL DEFAULT 0,
    approved_version BIGINT NOT NULL DEFAULT 0, draft_json TEXT NOT NULL DEFAULT '{}',
    approved_json TEXT, suspended BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS professional_document (
    id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id), kind VARCHAR(20) NOT NULL,
    content_type VARCHAR(30) NOT NULL, sha256 VARCHAR(64) NOT NULL, content BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_professional_document_user ON professional_document(user_id);
CREATE TABLE IF NOT EXISTS professional_submission (
    id UUID PRIMARY KEY, onboarding_id UUID NOT NULL REFERENCES professional_onboarding(id),
    revision BIGINT NOT NULL, base_approved_version BIGINT NOT NULL, snapshot_json TEXT NOT NULL,
    policy_json TEXT NOT NULL, status VARCHAR(30) NOT NULL, result_json TEXT, attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL, decided_at TIMESTAMPTZ,
    decided_by UUID REFERENCES users(id), decision_origin VARCHAR(10), decision_reason TEXT,
    UNIQUE(onboarding_id, revision)
);
CREATE INDEX IF NOT EXISTS idx_professional_submission_work ON professional_submission(status, available_at);
ALTER TABLE technician ALTER COLUMN crea DROP NOT NULL;

ALTER TABLE profession ADD COLUMN IF NOT EXISTS requires_nr10 boolean;
ALTER TABLE profession ADD COLUMN IF NOT EXISTS requires_nr35 boolean;

ALTER TABLE professional_document ALTER COLUMN content DROP NOT NULL;
ALTER TABLE professional_document ADD COLUMN IF NOT EXISTS cloudinary_public_id VARCHAR(255);
ALTER TABLE professional_document ADD COLUMN IF NOT EXISTS cloudinary_format VARCHAR(20);
