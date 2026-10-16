import argparse
import os
import sys
from datetime import date
from pathlib import Path

from .builder import build_dataset
from .images import DEFAULT_MANIFEST, ImagePool
from .loader import check_environment, connect, load_dataset, load_plan

DEFAULT_PLAN = Path(__file__).resolve().parent / 'plan.yaml'


def parse_args(argv):
    parser = argparse.ArgumentParser(prog='python -m seed', description='Seed inicial planejado (core e auth).')
    parser.add_argument('--plan', default=str(DEFAULT_PLAN))
    parser.add_argument('--manifest', default=str(DEFAULT_MANIFEST))
    parser.add_argument('--today', default=None, help='Data de referencia AAAA-MM-DD (padrao: hoje).')
    parser.add_argument('--dry-run', action='store_true', help='Monta o dataset e mostra o relatorio, sem tocar no banco.')
    parser.add_argument('--reset', action='store_true', help='Apaga apenas as linhas deste seed (IDs deterministicos).')
    parser.add_argument('--strict-images', action='store_true', help='Falha se algum pool de imagens nao tiver imagens suficientes.')
    parser.add_argument('--core-only', action='store_true', help='Nao toca no banco de auth.')
    return parser.parse_args(argv)


def print_report(dataset):
    print('Linhas por tabela:')
    for table, count in dataset.counts().items():
        print(f'  {table}: {count}')
    short = [row for row in dataset.image_report if row[3]]
    print(f'Pools de imagem com falta: {len(short)}')
    for category, requested, available, missing in short:
        print(f'  {category}: pedidas {requested}, disponiveis {available}, faltam {missing}')


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    plan = load_plan(args.plan)
    cloud = os.environ.get('CLOUDINARY_CLOUD_NAME')
    if not cloud and not args.dry_run and not args.reset:
        raise SystemExit('Defina CLOUDINARY_CLOUD_NAME (nome da cloud) para montar as URLs das imagens.')
    today = date.fromisoformat(args.today) if args.today else date.today()
    pool = ImagePool(args.manifest, plan['rng_seed'], cloud or 'CLOUD_NAME', plan['cloudinary']['public_prefix'])
    dataset = build_dataset(plan, pool, today)
    print_report(dataset)
    if args.strict_images and any(row[3] for row in dataset.image_report):
        raise SystemExit('Faltam imagens em alguns pools (--strict-images).')
    if args.dry_run:
        return 0
    check_environment(plan)
    core = connect('core')
    auth = None if args.core_only else connect('auth')
    try:
        summary = load_dataset(dataset, reset=args.reset, core_connection=core, auth_connection=auth)
    finally:
        core.close()
        if auth is not None:
            auth.close()
    verb = 'removidas' if args.reset else 'inseridas'
    print(f'Linhas {verb} (por tabela):')
    for table, count in summary.items():
        if count:
            print(f'  {table}: {count}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
