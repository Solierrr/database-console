ALTER TABLE model_photo ADD COLUMN IF NOT EXISTS is_primary BOOLEAN NOT NULL DEFAULT FALSE;

WITH ranked AS (
    SELECT id, ROW_NUMBER() OVER (PARTITION BY fk_model ORDER BY created_at DESC, id) AS position
    FROM model_photo
)
UPDATE model_photo SET is_primary = TRUE
FROM ranked
WHERE model_photo.id = ranked.id AND ranked.position = 1
  AND NOT EXISTS (
      SELECT 1 FROM model_photo AS current_primary
      WHERE current_primary.fk_model = model_photo.fk_model AND current_primary.is_primary
  );

CREATE UNIQUE INDEX IF NOT EXISTS uq_model_photo_primary ON model_photo (fk_model) WHERE is_primary;
