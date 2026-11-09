# Crops the shoot.js and draw.js captures to the card shape (16:10) and writes the module JPEGs.
# Usage: python make.py <rawdir> [outdir]   (outdir defaults to static/assets/img/modules)
import glob, json, os, sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RAW = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / 'static/assets/img/modules')
ASPECT = 1.6
CARD = (800, 500)
HERO = (1360, 850)

# number: (left, top, width), each a fraction of the capture. width None = as wide as 16:10 allows.
C = {
    '01': (0, 0, None), '02': (.19, .10, .62), '03': (0, 0, None), '04': (.01, .10, .78), '05': (.05, 0, None),
    '06': (.04, 0, None), '07': (0, 0, None), '08': (.05, 0, None), '09': (.02, .05, .80), '10': (0, 0, None),
    '11': (0, 0, None), '12': (.104, 0, None), '13': (0, .05, None), '14': (.104, 0, None), '15': (.104, 0, None),
    '16': (.104, 0, None), '17': (.104, 0, None), '18': (0, .05, None), '19': (.05, 0, None), '20': (.05, 0, None),
    '21': (.05, 0, None), '22': (0, 0, None), '23': (.05, 0, None), '24': (.05, 0, None), '25': (0, 0, None),
    '26': (0, 0, None), '27': (0, 0, None), '28': (0, 0, None), '29': (0, 0, None), '30': (0, 0, None),
    '31': (0, 0, None), '32': (0, 0, None), '33': (0, 0, None), '34': (0, 0, None),
}
for n in range(35, 44):  # drawn at the card shape by draw.js
    C[str(n)] = (0, 0, None)
HEROES = {'hero-rota-rod': '04', 'hero-plus-maze': '11', 'hero-dose-response': '12'}


def crop(im, spec):
    W, H = im.size
    left, top, w = spec
    if w is None:
        cw = min(W, H * ASPECT)
    else:
        cw = W * w
    ch = cw / ASPECT
    if ch > H:
        ch, cw = H, H * ASPECT
    x = min(W * left, W - cw)
    y = min(H * top, H - ch)
    return im.crop((round(x), round(y), round(x + cw), round(y + ch)))


os.makedirs(OUT, exist_ok=True)
slugs = {f'{m["no"]:02d}': m['slug'] for m in json.load(open(ROOT / 'lab/modules.json', encoding='utf-8'))}
for n, slug in slugs.items():
    im = Image.open(f'{RAW}/{n}.png').convert('RGB')
    crop(im, C[n]).resize(CARD, Image.LANCZOS).save(f'{OUT}/{slug}.jpg', quality=82, optimize=True, progressive=True)
for name, n in HEROES.items():
    im = Image.open(f'{RAW}/{n}.png').convert('RGB')
    crop(im, C[n]).resize(HERO, Image.LANCZOS).save(f'{OUT}/{name}.jpg', quality=85, optimize=True, progressive=True)
total = sum(os.path.getsize(f) for f in glob.glob(OUT + '/*.jpg'))
print(len(glob.glob(OUT + '/*.jpg')), 'files', round(total / 1e6, 2), 'MB')
