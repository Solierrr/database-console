-- Projects support company/professional ownership; preserve existing technical-service references.
ALTER TABLE technical_project ALTER COLUMN fk_requester DROP NOT NULL;
ALTER TABLE technical_project ALTER COLUMN fk_local_unit DROP NOT NULL;
ALTER TABLE technical_project ALTER COLUMN start_date DROP NOT NULL;
ALTER TABLE technical_project ADD COLUMN name varchar(160) NOT NULL DEFAULT 'Projeto técnico', ADD COLUMN description text, ADD COLUMN owner_company_id uuid REFERENCES company(id), ADD COLUMN owner_user_id uuid REFERENCES users(id), ADD COLUMN created_by uuid REFERENCES users(id), ADD COLUMN archived boolean NOT NULL DEFAULT false, ADD COLUMN created_at timestamptz NOT NULL DEFAULT now(), ADD COLUMN version bigint NOT NULL DEFAULT 0,
 ADD COLUMN location_state varchar(2), ADD COLUMN location_city varchar(120), ADD COLUMN location_neighborhood varchar(120), ADD COLUMN location_zip_code varchar(8), ADD COLUMN location_street varchar(180), ADD COLUMN location_number varchar(30), ADD COLUMN location_complement varchar(180);
UPDATE technical_project p SET owner_company_id=r.fk_company FROM requester r WHERE r.id=p.fk_requester;
ALTER TABLE technical_project ADD CONSTRAINT ck_project_owner CHECK ((owner_company_id IS NOT NULL)::integer + (owner_user_id IS NOT NULL)::integer = 1);
CREATE TABLE project_member (id uuid PRIMARY KEY,version bigint NOT NULL DEFAULT 0,project_id uuid NOT NULL REFERENCES technical_project(id),user_id uuid NOT NULL REFERENCES users(id),role varchar(16) NOT NULL CHECK(role IN ('OWNER','MANAGER','MEMBER','VIEWER')),function_name varchar(120),active boolean NOT NULL DEFAULT true,joined_at timestamptz NOT NULL DEFAULT now(),UNIQUE(project_id,user_id));
CREATE TABLE project_invitation (id uuid PRIMARY KEY,version bigint NOT NULL DEFAULT 0,project_id uuid NOT NULL REFERENCES technical_project(id),recipient_auth_id uuid,email varchar(254) NOT NULL,role varchar(16) NOT NULL CHECK(role IN ('MANAGER','MEMBER','VIEWER')),function_name varchar(120),status varchar(16) NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','ACCEPTED','DECLINED','REVOKED')),expires_at timestamptz NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),created_by uuid NOT NULL REFERENCES users(id),locale varchar(5) NOT NULL DEFAULT 'pt-BR',email_state varchar(16) NOT NULL DEFAULT 'PENDING',email_attempts integer NOT NULL DEFAULT 0,next_email_attempt_at timestamptz,responded_at timestamptz);
CREATE TABLE project_activity (id uuid PRIMARY KEY,version bigint NOT NULL DEFAULT 0,project_id uuid NOT NULL REFERENCES technical_project(id),title varchar(160) NOT NULL,description text,type varchar(16) NOT NULL CHECK(type IN ('SERVICE','VISIT','MEETING','OTHER')),status varchar(16) NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','IN_PROGRESS','COMPLETED','CANCELED')),starts_at timestamptz NOT NULL,ends_at timestamptz,onsite boolean NOT NULL DEFAULT false,assignee_ids uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],technical_service_id uuid REFERENCES technical_service(id),CHECK(ends_at IS NULL OR ends_at>starts_at));
CREATE TABLE project_history (id uuid PRIMARY KEY,version bigint NOT NULL DEFAULT 0,project_id uuid NOT NULL REFERENCES technical_project(id),actor_id uuid NOT NULL REFERENCES users(id),action varchar(40) NOT NULL,detail text NOT NULL,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE project_photo (id uuid PRIMARY KEY,version bigint NOT NULL DEFAULT 0,project_id uuid NOT NULL REFERENCES technical_project(id),name varchar(160) NOT NULL,mime varchar(40) NOT NULL CHECK(mime IN ('image/jpeg','image/png')),content bytea NOT NULL CHECK(octet_length(content)<=8388608),cover boolean NOT NULL DEFAULT false,uploaded_by uuid NOT NULL REFERENCES users(id),created_at timestamptz NOT NULL DEFAULT now());
CREATE UNIQUE INDEX uq_project_photo_cover ON project_photo(project_id) WHERE cover;
CREATE INDEX ix_project_company ON technical_project(owner_company_id,created_at DESC);
CREATE INDEX ix_project_personal ON technical_project(owner_user_id,created_at DESC);
CREATE INDEX ix_project_member_access ON project_member(user_id,project_id) WHERE active;
CREATE INDEX ix_project_invitation_recipient ON project_invitation(lower(email),status,expires_at);
CREATE INDEX ix_project_activity_agenda ON project_activity(project_id,starts_at);
CREATE INDEX ix_project_history_timeline ON project_history(project_id,created_at DESC);
CREATE INDEX ix_project_photo_gallery ON project_photo(project_id,created_at DESC);
-- New company permission is evaluated by ProjectAccess, while personal operations use project roles.
INSERT INTO permission(id,permission_name,name,description) VALUES(gen_random_uuid(),'POST /api/projects','Criar projetos','Criar projetos no contexto empresarial') ON CONFLICT(permission_name) DO NOTHING;

-- Existing service_status enum values are preserved; varchar matches the JPA string mapping.
ALTER TABLE technical_project ALTER COLUMN status DROP DEFAULT;
ALTER TABLE technical_project ALTER COLUMN status TYPE varchar(20) USING status::text;
ALTER TABLE technical_project ALTER COLUMN status SET DEFAULT 'OPEN';
ALTER TABLE technical_project ADD CONSTRAINT ck_project_status CHECK(status IN ('OPEN','IN_PROGRESS','COMPLETED','CANCELED'));
ALTER TABLE technical_service ALTER COLUMN status DROP DEFAULT;
ALTER TABLE technical_service ALTER COLUMN status TYPE varchar(20) USING status::text;
ALTER TABLE technical_service ALTER COLUMN status SET DEFAULT 'OPEN';
ALTER TABLE technical_service ADD CONSTRAINT ck_service_status CHECK(status IN ('OPEN','IN_PROGRESS','COMPLETED','CANCELED'));

UPDATE technical_project p SET location_state=a.state,location_city=left(a.city,120),
 location_neighborhood=left(a.neighborhood,120),location_zip_code=a.zip_code,
 location_street=left(a.street,180),location_number=a.number,location_complement=left(u.complement,180)
FROM local_unit u JOIN address a ON a.id=u.fk_address WHERE p.fk_local_unit=u.id;
INSERT INTO project_member(id,project_id,user_id,role,function_name)
SELECT gen_random_uuid(),s.fk_technical_project,person.fk_users,'MEMBER',left(min(e.function),120)
FROM service_executor e JOIN technical_service s ON s.id=e.fk_service
JOIN technician_affiliation affiliation ON affiliation.id=e.fk_technician_affiliation
JOIN technician technician ON technician.id=affiliation.fk_technician
JOIN person person ON person.id=technician.fk_person
WHERE person.fk_users IS NOT NULL GROUP BY s.fk_technical_project,person.fk_users
ON CONFLICT(project_id,user_id) DO NOTHING;

-- Approved independent professionals can execute work without a company affiliation.
ALTER TABLE technician_affiliation ALTER COLUMN fk_company DROP NOT NULL;
ALTER TABLE technician_affiliation ALTER COLUMN affiliation_type TYPE varchar(16) USING affiliation_type::text;
ALTER TABLE technician_affiliation ADD CONSTRAINT ck_affiliation_type CHECK(affiliation_type IN ('INDEPENDENT','AFFILIATED','PARTNER'));
ALTER TABLE technician_affiliation ADD CONSTRAINT ck_affiliation_company CHECK(fk_company IS NOT NULL OR affiliation_type='INDEPENDENT');
CREATE UNIQUE INDEX uq_active_independent_affiliation ON technician_affiliation(fk_technician) WHERE active AND fk_company IS NULL AND affiliation_type='INDEPENDENT';

-- Preserve the technical-service history in the agenda without fabricating missing end times.
CREATE UNIQUE INDEX uq_project_activity_service ON project_activity(technical_service_id) WHERE technical_service_id IS NOT NULL;
INSERT INTO project_activity(id,project_id,title,type,status,starts_at,ends_at,assignee_ids,technical_service_id)
SELECT gen_random_uuid(),s.fk_technical_project,left(s.purpose,160),'SERVICE',s.status,
 coalesce(s.scheduled_date,s.created_at),
 CASE WHEN s.end_date>coalesce(s.scheduled_date,s.created_at) THEN s.end_date ELSE NULL END,
 coalesce((SELECT array_agg(DISTINCT person.fk_users) FROM service_executor e
 JOIN technician_affiliation a ON a.id=e.fk_technician_affiliation
 JOIN technician t ON t.id=a.fk_technician JOIN person person ON person.id=t.fk_person
 WHERE e.fk_service=s.id AND person.fk_users IS NOT NULL),ARRAY[]::uuid[]),s.id
FROM technical_service s;
