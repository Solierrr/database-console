ALTER TABLE professional_document ALTER COLUMN content_type TYPE VARCHAR(100);
ALTER TABLE professional_document ADD COLUMN IF NOT EXISTS original_file_name VARCHAR(255);
