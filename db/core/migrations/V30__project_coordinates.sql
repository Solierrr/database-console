ALTER TABLE technical_project
    ADD COLUMN location_latitude double precision,
    ADD COLUMN location_longitude double precision,
    ADD COLUMN location_place_id varchar(300),
    ADD COLUMN location_geocoded_at timestamptz;

ALTER TABLE technical_project ADD CONSTRAINT project_coordinates_valid CHECK (
    (location_latitude IS NULL AND location_longitude IS NULL)
    OR (location_latitude IS NOT NULL AND location_longitude IS NOT NULL
        AND location_latitude BETWEEN -90 AND 90 AND location_longitude BETWEEN -180 AND 180)
);
