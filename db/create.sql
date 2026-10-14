\set ON_ERROR_STOP on

SELECT format('CREATE DATABASE %I', :'DB')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'DB')
\gexec
