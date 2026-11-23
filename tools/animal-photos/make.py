"""Make the web sprites of the albino mouse and rat from the photographs in src/ (already cut out on transparency).

    python tools/animal-photos/make.py

Writes the mouse and rat views and the handling holds (hold-*) to static/assets/img/animals/ at reduced resolution. animal-art.js
draws each image at the photo's original pixel size, so its maps and masks stay in the photo's pixel coordinates.
"""
from pathlib import Path
from PIL import Image

HERE = Path(__file__).parent
OUT = HERE.parent.parent / 'static' / 'assets' / 'img' / 'animals'
JOBS = {'mouse-side-r': ('mouse-side', .7), 'mouse-top': ('mouse-top-photo', .6), 'rat-top': ('rat-top-photo', .6), 'mouse-front': ('mouse-front-photo', .5),
        # photographs of the handling holds, for the restraint and handling scenes (hold-scruff-upright-b is a spare)
        'hold-scruff-sc': ('hold-scruff-sc', .55), 'hold-scruff-im': ('hold-scruff-im', .5), 'hold-scruff-tilt': ('hold-scruff-tilt', .55),
        'hold-scruff-upright': ('hold-scruff-upright', .6), 'hold-restrainer': ('hold-restrainer', .5), 'hold-tail': ('hold-tail', .35)}
for src, (name, k) in JOBS.items():
    im = Image.open(HERE / 'src' / f'{src}.webp').convert('RGBA')
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    im.save(OUT / f'{name}.webp', quality=88, method=6)
    print(name, im.size, (OUT / f'{name}.webp').stat().st_size)
