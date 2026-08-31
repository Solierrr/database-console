-- Popula o catalogo a partir do schema atual e anota manualmente as
-- colunas mais sensiveis/criticas com regra de negocio e nivel de acesso.

CALL sp_refresh_data_catalog();

UPDATE data_catalog SET access_level = 'CONFIDENTIAL', business_rule =
    'Hash de senha (bcrypt/argon2). Nunca deve ser exposto por API ou relatorio.'
    WHERE table_name = 'local_credential' AND column_name = 'password_hash';

UPDATE data_catalog SET access_level = 'CONFIDENTIAL', business_rule =
    'Segredo TOTP cifrado. Acesso restrito a rotina de autenticacao MFA.'
    WHERE table_name = 'totp_factor' AND column_name IN ('secret_ciphertext', 'secret_nonce');

UPDATE data_catalog SET access_level = 'RESTRICTED', business_rule =
    'E-mail principal da conta, case-insensitive (citext), usado para login. Unico por conta.'
    WHERE table_name = 'auth_user' AND column_name = 'primary_email';

UPDATE data_catalog SET access_level = 'RESTRICTED', business_rule =
    'CPF do titular. Documento pessoal, uso restrito a validacao de identidade.'
    WHERE table_name = 'person' AND column_name = 'cpf';

UPDATE data_catalog SET access_level = 'RESTRICTED', business_rule =
    'CNPJ da empresa. Usado para validacao de cadastro e emissao fiscal.'
    WHERE table_name = 'company' AND column_name = 'cnpj';

UPDATE data_catalog SET access_level = 'INTERNAL', business_rule =
    'Payload livre do evento de dominio (outbox pattern). Pode conter dados de negocio variados.'
    WHERE table_name = 'outbox_event' AND column_name = 'payload';

UPDATE data_catalog SET access_level = 'INTERNAL', business_rule =
    'Detalhes contextuais do evento de seguranca (IP, dispositivo, motivo). Usado para auditoria e resposta a incidentes.'
    WHERE table_name = 'security_event' AND column_name = 'details';

UPDATE data_catalog SET access_level = 'INTERNAL', business_rule =
    'Valor total calculado a partir dos itens da proposta (ver fn_proposal_total); nao deve ser editado manualmente.'
    WHERE table_name = 'proposal' AND column_name = 'total_amount';

UPDATE data_catalog SET access_level = 'INTERNAL', business_rule =
    'Preco de tabela da oferta; alteracoes exigem aprovacao comercial do supplier.'
    WHERE table_name = 'offer' AND column_name = 'unit_price';

UPDATE data_catalog SET access_level = 'RESTRICTED', business_rule =
    'Referencia 1:1 para auth_user.id no banco de autenticacao; chave de correlacao entre os dominios identity e auth.'
    WHERE table_name = 'users' AND column_name = 'fk_auth_user';
