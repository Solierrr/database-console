"""Confere se `db/auth/migrations` é espelho fiel das migrations Flyway do api-auth (T-031).

O `authdb` tem um autor, o `api-auth` (`src/main/resources/db/migration`), e um executor nos
ambientes, este repositório (`scripts/migrate.py --target auth`), com o Flyway do `api-auth`
desligado (`SPRING_FLYWAY_ENABLED=false`). Para as duas pontas não divergirem, os arquivos daqui
precisam ter o mesmo SQL dos de lá. Comentários no início do arquivo são ignorados na comparação.

  python scripts/check_auth_mirror.py [pasta-do-api-auth]      (padrão: $API_AUTH_DIR ou ../api-auth)

Sai com 1 se faltar, sobrar ou diferir algum arquivo.
"""
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MIRROR = ROOT / 'db' / 'auth' / 'migrations'
SOURCE_SUBDIR = Path('src/main/resources/db/migration')
NAME = re.compile(r'V(\d+)__.+\.sql')


def normalize(text):
    """Sem CRLF e sem o bloco de comentários `--` do começo do arquivo."""
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    start = 0
    while start < len(lines) and (not lines[start].strip() or lines[start].lstrip().startswith('--')):
        start += 1
    return '\n'.join(line.rstrip() for line in lines[start:]).strip()


def migrations(folder):
    return {path.name: normalize(path.read_text(encoding='utf-8-sig'))
            for path in sorted(Path(folder).glob('V*__*.sql')) if NAME.fullmatch(path.name)}


def compare(source_dir, mirror_dir=MIRROR):
    source, mirror = migrations(source_dir), migrations(mirror_dir)
    problems = []
    for name in sorted(source.keys() - mirror.keys()):
        problems.append(f'Falta no espelho: {name}')
    for name in sorted(mirror.keys() - source.keys()):
        problems.append(f'Sobra no espelho (não existe no api-auth): {name}')
    for name in sorted(source.keys() & mirror.keys()):
        if source[name] != mirror[name]:
            problems.append(f'Conteúdo diferente: {name}')
    return problems


def main(argv):
    api_auth = Path(argv[1] if len(argv) > 1 else os.environ.get('API_AUTH_DIR') or ROOT.parent / 'api-auth')
    source_dir = api_auth / SOURCE_SUBDIR
    if not source_dir.is_dir():
        print(f'Não achei {source_dir}. Passe a pasta do api-auth ou defina API_AUTH_DIR.')
        return 2
    problems = compare(source_dir)
    for problem in problems:
        print(problem)
    print('OK: o espelho do authdb bate com o api-auth.' if not problems else f'{len(problems)} divergência(s).')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
