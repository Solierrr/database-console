-- Entidades compartilhadas entre varios dominios: endereco, contato,
-- geolocalizacao e o supertype de midia (herenca de tabelas para os
-- 4 padroes de "foto" repetidos no dominio original: model_photo,
-- company_photo, user_photo, local_unit_photo).

CREATE TABLE address (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state CHAR(2) NOT NULL,
    city VARCHAR(120) NOT NULL,
    neighborhood VARCHAR(120),
    zip_code CHAR(8) NOT NULL,
    street VARCHAR(200) NOT NULL,
    number VARCHAR(10)
);

CREATE TABLE contact (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(100),
    phone VARCHAR(12)
);

CREATE TABLE geolocalization (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_address UUID REFERENCES address (id),
    latitude NUMERIC(10, 7) NOT NULL,
    longitude NUMERIC(10, 7) NOT NULL
);

-- Supertype de midia: cada tabela de foto especifica (subtype) referencia
-- media_asset pelo mesmo id (padrao classico de Table Inheritance / Class
-- Table Inheritance), evitando repetir url/public_id/created_at 4 vezes.
CREATE TABLE media_asset (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    public_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
