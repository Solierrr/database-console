-- Recorte (ponto focal) das fotos: retangulo em pixels da imagem original. Nulo nos quatro = automatico.
ALTER TABLE user_photo ADD COLUMN IF NOT EXISTS crop_x INTEGER;
ALTER TABLE user_photo ADD COLUMN IF NOT EXISTS crop_y INTEGER;
ALTER TABLE user_photo ADD COLUMN IF NOT EXISTS crop_width INTEGER;
ALTER TABLE user_photo ADD COLUMN IF NOT EXISTS crop_height INTEGER;
ALTER TABLE user_photo ADD CONSTRAINT ck_user_photo_crop CHECK (
    (crop_x IS NULL AND crop_y IS NULL AND crop_width IS NULL AND crop_height IS NULL)
    OR (crop_x IS NOT NULL AND crop_y IS NOT NULL AND crop_width IS NOT NULL AND crop_height IS NOT NULL
        AND crop_x >= 0 AND crop_y >= 0 AND crop_width > 0 AND crop_height > 0)
);

ALTER TABLE company_photo ADD COLUMN IF NOT EXISTS crop_x INTEGER;
ALTER TABLE company_photo ADD COLUMN IF NOT EXISTS crop_y INTEGER;
ALTER TABLE company_photo ADD COLUMN IF NOT EXISTS crop_width INTEGER;
ALTER TABLE company_photo ADD COLUMN IF NOT EXISTS crop_height INTEGER;
ALTER TABLE company_photo ADD CONSTRAINT ck_company_photo_crop CHECK (
    (crop_x IS NULL AND crop_y IS NULL AND crop_width IS NULL AND crop_height IS NULL)
    OR (crop_x IS NOT NULL AND crop_y IS NOT NULL AND crop_width IS NOT NULL AND crop_height IS NOT NULL
        AND crop_x >= 0 AND crop_y >= 0 AND crop_width > 0 AND crop_height > 0)
);
