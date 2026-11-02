-- Execute with `make schema TARGET=analytics ENVIRONMENT=prod` after creating analyticsdb.
-- The exporter creates the KPI tables from the published Gold view schemas.
CREATE SCHEMA IF NOT EXISTS gold;
REVOKE ALL ON SCHEMA gold FROM PUBLIC;

CREATE TABLE IF NOT EXISTS gold.principal_access (
    principal TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('ADMIN', 'EXPORTER', 'READER', 'SUPPLIER', 'REQUESTER', 'PROFESSIONAL')),
    entity_id TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    validated_by TEXT NOT NULL,
    validated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (principal, scope, entity_id)
);
REVOKE ALL ON gold.principal_access FROM PUBLIC;
-- Keeps databases created before the READER scope in line with the current list.
ALTER TABLE gold.principal_access DROP CONSTRAINT IF EXISTS principal_access_scope_check;
ALTER TABLE gold.principal_access ADD CONSTRAINT principal_access_scope_check
    CHECK (scope IN ('ADMIN', 'EXPORTER', 'READER', 'SUPPLIER', 'REQUESTER', 'PROFESSIONAL'));

-- Two ways to be authorized:
--   1. session_user: the actual login, even inside this SECURITY DEFINER function. A non-admin
--      principal can map to only one entity per scope (registry above).
--   2. Request context: one shared reader login (the api-core) runs each request in a transaction
--      that first calls set_config('gold.scope', ..., true) and set_config('gold.entity_id', ..., true).
--      The context only authorizes principals registered as READER, so a login that is not in the
--      registry cannot widen its access by setting the values itself.
CREATE OR REPLACE FUNCTION gold.can_read(requested_scope TEXT, requested_id TEXT)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
    SELECT session_user = pg_get_userbyid(
        (SELECT proowner FROM pg_proc
         WHERE oid = 'gold.can_read(text,text)'::regprocedure)
    )
    OR EXISTS (
        SELECT 1 FROM gold.principal_access a
        WHERE a.principal = session_user AND a.scope = 'EXPORTER'
          AND a.entity_id = '*' AND a.active
    )
    OR EXISTS (
        SELECT 1 FROM gold.principal_access a
        WHERE a.principal = session_user AND a.scope = 'ADMIN'
          AND a.entity_id = '*' AND a.active
    )
    OR (
        requested_scope <> 'ADMIN' AND
        (SELECT COUNT(DISTINCT a.entity_id) = 1
                AND MAX(a.entity_id) = requested_id
         FROM gold.principal_access a
         WHERE a.principal = session_user AND a.scope = requested_scope
           AND a.active)
    )
    OR (
        EXISTS (
            SELECT 1 FROM gold.principal_access a
            WHERE a.principal = session_user AND a.scope = 'READER'
              AND a.entity_id = '*' AND a.active
        )
        AND NULLIF(pg_catalog.current_setting('gold.scope', true), '') IS NOT NULL
        AND (
            (pg_catalog.current_setting('gold.scope', true) = 'ADMIN'
             AND pg_catalog.current_setting('gold.entity_id', true) = '*')
            OR (requested_scope <> 'ADMIN'
                AND pg_catalog.current_setting('gold.scope', true) = requested_scope
                AND pg_catalog.current_setting('gold.entity_id', true) = requested_id)
        )
    );
$function$;
REVOKE ALL ON FUNCTION gold.can_read(TEXT, TEXT) FROM PUBLIC;
