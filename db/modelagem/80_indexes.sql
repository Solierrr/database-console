-- Índices justificados por EXPLAIN ANALYZE (ver docs/OTIMIZACAO.md).

-- Consultas por situação e período (por exemplo propostas aceitas dos últimos 60 dias):
-- 62 ms com varredura sequencial caíram para 3,7 ms com este índice, em 150 mil propostas.
CREATE INDEX IF NOT EXISTS idx_proposal_status_created_at ON proposal (status, created_at);
