ALTER TABLE auth_session ADD COLUMN client_id VARCHAR(100) NOT NULL DEFAULT 'solaria-web';
ALTER TABLE auth_session ADD COLUMN context VARCHAR(30) NOT NULL DEFAULT 'web';
CREATE TABLE mobile_auth_transaction (
    id VARCHAR(43) PRIMARY KEY, client_id VARCHAR(100) NOT NULL, redirect_uri TEXT NOT NULL,
    state VARCHAR(128) NOT NULL, code_challenge VARCHAR(43) NOT NULL, status VARCHAR(30) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL, user_id UUID REFERENCES auth_user(id),
    authorizing_session_id UUID REFERENCES auth_session(id), code_hash BYTEA UNIQUE,
    code_expires_at TIMESTAMPTZ, consumed_at TIMESTAMPTZ
);
CREATE INDEX idx_mobile_transaction_expiry ON mobile_auth_transaction(expires_at);
