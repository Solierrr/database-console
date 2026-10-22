ALTER TABLE offer ADD COLUMN commercial_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE offer ADD CONSTRAINT ck_offer_commercial_status CHECK (commercial_status IN ('ACTIVE','PAUSED','CLOSED'));
CREATE TABLE offer_status_history (
    id UUID PRIMARY KEY, offer_id UUID NOT NULL REFERENCES offer(id),
    previous_status VARCHAR(16) NOT NULL CHECK (previous_status IN ('ACTIVE','PAUSED','CLOSED')),
    new_status VARCHAR(16) NOT NULL CHECK (new_status IN ('ACTIVE','PAUSED','CLOSED')),
    actor_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_offer_history_transition CHECK (previous_status <> new_status)
);
CREATE INDEX idx_offer_status_history_offer ON offer_status_history(offer_id, created_at DESC);
