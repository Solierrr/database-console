import io
import json
import random
from collections import Counter
from functools import lru_cache
from pathlib import Path

DEFAULT_MANIFEST = Path(__file__).resolve().parents[2] / 'mocks-warehouse' / 'manifest.json'


@lru_cache(maxsize=1024)
def _to_jpeg(source, max_edge, quality):
    try:
        from PIL import Image
    except ImportError as error:  # pragma: no cover - depende do ambiente
        raise SystemExit('Fotos de projeto exigem Pillow: python -m pip install -r scripts/requirements.txt') from error
    with Image.open(source) as image:
        image = image.convert('RGB')
        image.thumbnail((max_edge, max_edge))
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=quality, optimize=True)
    return buffer.getvalue()


class ImagePool:
    """Sorteia imagens do manifest do mocks-warehouse por categoria.

    `unique` nunca devolve a mesma imagem duas vezes (por categoria); `sample`/`repeat` podem repetir entre
    entidades. Quando um pool acaba, a falta e registrada em `shortages` e o chamador recebe None.
    """

    def __init__(self, manifest_path, seed, cloud_name, prefix='mocks'):
        assets = json.loads(Path(manifest_path).read_text(encoding='utf-8'))['assets']
        self.cloud_name = cloud_name
        self.prefix = prefix
        self.root = Path(manifest_path).resolve().parent
        self.by_category = {}
        self.crops = {}
        self.paths = {}
        for asset in assets:
            self.by_category.setdefault(asset['category'], []).append(asset['id'])
            if asset.get('path'):
                self.paths[asset['id']] = asset['path']
            crop = asset.get('attributes', {}).get('crop')
            if crop:
                self.crops[asset['id']] = crop
        for category, ids in self.by_category.items():
            ids.sort()
            random.Random(f'{seed}:{category}').shuffle(ids)
        self.cursor = Counter()
        self.needed = Counter()

    def available(self, category):
        return len(self.by_category.get(category, []))

    def unique(self, category):
        self.needed[category] += 1
        ids = self.by_category.get(category, [])
        position = self.cursor[category]
        if position >= len(ids):
            return None
        self.cursor[category] += 1
        return ids[position]

    def repeat(self, category, rng):
        self.needed[category] = max(self.needed[category], 1)
        ids = self.by_category.get(category, [])
        return rng.choice(ids) if ids else None

    def repeat_any(self, categories, rng):
        for category in categories:
            self.needed[category] = max(self.needed[category], 1)
        pooled = [image for category in categories for image in self.by_category.get(category, [])]
        return rng.choice(sorted(pooled)) if pooled else None

    def sample(self, category, count, rng):
        self.needed[category] = max(self.needed[category], count)
        ids = self.by_category.get(category, [])
        return rng.sample(ids, min(count, len(ids)))

    def crop_columns(self, asset_id):
        crop = self.crops.get(asset_id)
        if not crop:
            # sempre as quatro colunas: o loader exige o mesmo conjunto de colunas em todas as linhas da tabela
            return {'crop_x': None, 'crop_y': None, 'crop_width': None, 'crop_height': None}
        return {'crop_x': crop['x'], 'crop_y': crop['y'], 'crop_width': crop['width'], 'crop_height': crop['height']}

    def jpeg_bytes(self, asset_id, max_edge=1200, quality=72):
        """JPEG da imagem do mocks-warehouse. Fotos de projeto ficam no banco como bytes e a API so aceita JPG ou PNG
        (ate 8 MB), enquanto o catalogo e WebP. None se o arquivo nao existir (manifest sintetico dos testes)."""
        relative = self.paths.get(asset_id)
        source = self.root / relative if relative else None
        if source is None or not source.is_file():
            return None
        return _to_jpeg(str(source), max_edge, quality)

    def public_id(self, asset_id):
        return f'{self.prefix}/{asset_id}'

    def url(self, asset_id):
        return f'https://res.cloudinary.com/{self.cloud_name}/image/upload/{self.prefix}/{asset_id}.webp'

    def report(self):
        # (categoria, necessarias, disponiveis, faltam); galerias e banners de usuario podem repetir, entao
        # contam o tamanho minimo do pool e nao o numero de usos
        return [(category, self.needed[category], self.available(category), max(0, self.needed[category] - self.available(category)))
                for category in sorted(self.needed)]
