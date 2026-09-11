\set ON_ERROR_STOP on

SELECT format('DROP DATABASE IF EXISTS %I', : 'DB')
\gexec

SELECT format('CREATE DATABASE %I', : 'DB')
\gexec