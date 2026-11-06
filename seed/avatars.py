import hashlib

SELECT_WITHOUT_AVATAR = """
SELECT u.id,
       EXISTS (SELECT 1 FROM platform_admin pa WHERE pa.user_id = u.id),
       EXISTS (SELECT 1 FROM person p JOIN technician t ON t.person_id = p.id WHERE p.user_id = u.id),
       EXISTS (SELECT 1 FROM user_company uc JOIN job_position jp ON jp.id = uc.job_position_id
               WHERE uc.user_id = u.id AND jp.name = 'ADMIN')
FROM user_account u
WHERE u.avatar IS NULL
ORDER BY u.id
"""


def category_for(is_platform_admin, is_technician, is_company_admin):
    if is_platform_admin:
        return 'users/pfp/staff'
    if is_technician:
        return 'users/pfp/professionals'
    return 'users/pfp/suitman' if is_company_admin else 'users/pfp/clients'


def pick(ids, used, user_id):
    """Imagem ainda nao usada primeiro; acabando o pool, repete de forma deterministica (sem sortear)."""
    free = [image for image in ids if image not in used]
    if free:
        return free[0]
    digest = hashlib.sha256(str(user_id).encode()).digest()
    return ids[int.from_bytes(digest[:4], 'big') % len(ids)]


def backfill_avatars(pool, connection):
    """Da foto de perfil aos usuarios que ainda nao tem, sem tocar nos que ja tem.

    O seed nunca atualiza linhas existentes e o pool de fotos de pessoas e menor que o numero de usuarios, entao
    quem sobra recebe uma foto repetida do grupo certo (equipe da plataforma, profissionais, administradores de
    empresa ou demais). Devolve quantos usuarios receberam foto.
    """
    cursor = connection.cursor()
    cursor.execute('SELECT url FROM user_photo WHERE type = %s', ('PROFILE',))
    used_urls = {row[0] for row in cursor.fetchall()}
    cursor.execute(SELECT_WITHOUT_AVATAR)
    users = cursor.fetchall()
    used = {image for category in pool.by_category for image in pool.by_category[category] if pool.url(image) in used_urls}
    done = 0
    for user_id, is_platform_admin, is_technician, is_company_admin in users:
        ids = pool.by_category.get(category_for(is_platform_admin, is_technician, is_company_admin)) or []
        if not ids:
            continue
        image = pick(ids, used, user_id)
        used.add(image)
        crop = pool.crop_columns(image)
        cursor.execute('UPDATE user_account SET avatar = %s WHERE id = %s', (pool.url(image), user_id))
        cursor.execute('DELETE FROM user_photo WHERE user_id = %s AND type = %s', (user_id, 'PROFILE'))
        cursor.execute(
            'INSERT INTO user_photo (user_id, type, url, public_id, crop_x, crop_y, crop_width, crop_height) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
            (user_id, 'PROFILE', pool.url(image), pool.public_id(image), crop['crop_x'], crop['crop_y'],
             crop['crop_width'], crop['crop_height']),
        )
        done += 1
    connection.commit()
    return done


def backfill_company_photos(pool, connection):
    """Mesma ideia para empresas: logo (PROFILE) e banner (BANNER) das que ainda nao tem. Devolve (logos, banners)."""
    cursor = connection.cursor()
    banner_ids = sorted(image for category, ids in pool.by_category.items() if category.startswith('enterprises/banners/') for image in ids)
    logo_ids = pool.by_category.get('enterprises/pfp') or []
    counts = []
    for kind, ids in (('PROFILE', logo_ids), ('BANNER', banner_ids)):
        cursor.execute('SELECT url FROM company_photo WHERE type = %s', (kind,))
        used_urls = {row[0] for row in cursor.fetchall()}
        used = {image for image in ids if pool.url(image) in used_urls}
        cursor.execute(
            'SELECT c.id FROM company c WHERE NOT EXISTS '
            '(SELECT 1 FROM company_photo p WHERE p.company_id = c.id AND p.type = %s) ORDER BY c.id', (kind,))
        done = 0
        for (company_id,) in cursor.fetchall():
            if not ids:
                break
            image = pick(ids, used, company_id)
            used.add(image)
            crop = pool.crop_columns(image)
            cursor.execute(
                'INSERT INTO company_photo (company_id, type, url, public_id, crop_x, crop_y, crop_width, crop_height) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                (company_id, kind, pool.url(image), pool.public_id(image), crop['crop_x'], crop['crop_y'],
                 crop['crop_width'], crop['crop_height']),
            )
            done += 1
        counts.append(done)
    connection.commit()
    return tuple(counts)
