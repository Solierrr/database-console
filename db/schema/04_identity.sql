-- Dominio de identidade/RBAC (espelha api-core.identity).

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_auth_user UUID NOT NULL UNIQUE REFERENCES auth_user (id),
    avatar TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE person (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_user UUID REFERENCES users (id),
    fk_contact UUID REFERENCES contact (id),
    name VARCHAR(60) NOT NULL,
    cpf CHAR(11) NOT NULL,
    birth_date DATE NOT NULL
);

CREATE TABLE position (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(12) NOT NULL,
    accesses TEXT NOT NULL
);

CREATE TABLE permission (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    permission_name VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    description VARCHAR(300) NOT NULL
);

-- N:N entre position e permission.
CREATE TABLE position_permission (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_position UUID NOT NULL REFERENCES position (id),
    fk_permission UUID NOT NULL REFERENCES permission (id),
    UNIQUE (fk_position, fk_permission)
);

-- Subtype 1:1 de media_asset.
CREATE TABLE user_photo (
    id UUID PRIMARY KEY REFERENCES media_asset (id) ON DELETE CASCADE,
    fk_user UUID NOT NULL REFERENCES users (id),
    type photo_type NOT NULL
);
