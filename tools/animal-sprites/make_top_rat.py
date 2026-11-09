"""Build the top-view albino rat by reshaping the top-view mouse render.

No rat render exists yet, so this is the mouse with rat proportions, not a picture
of a rat: longer trunk and heavier body, longer head with a blunter muzzle, smaller
ears and eyes, larger feet. It keeps the photographic fur. Replace the output if a
real rat render becomes available.

    python tools/animal-sprites/make_top_rat.py static/assets/img/animals/top-mouse.webp static/assets/img/animals/top-rat.webp

Needs Pillow, numpy and scipy. Prints the sprite box to use in animal-art.js.
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

# All positions are pixels in top-mouse.webp (685 x 305). The body axis is y = 153.
AXIS = 153
RUMP, NOSE = 13, 673
# x in the mouse -> x in the rat: the trunk stretches most, the head a little
X_MOUSE = [0, 13, 440, 560, 685]
X_RAT = [16, 29, 533, 664, 798]
# half-width multiplier along the body: heavier trunk, then a blunter muzzle
Y_AT = [0, 60, 420, 520, 610, 650, 685]
Y_SCALE = [1.10, 1.12, 1.12, 1.12, 1.17, 1.25, 1.32]
# local features: centre x, y, radius of the feature, radius where the warp ends, resulting size
FEATURES = [
    (485, 95, 48, 72, .74), (485, 207, 48, 72, .74),            # ears, shrunk towards their base
    (585, 113, 12, 28, .8), (585, 187, 12, 28, .8),             # eyes
    (218, 30, 34, 62, 1.28), (205, 295, 34, 62, 1.28),          # hind feet
    (445, 48, 28, 50, 1.18), (450, 265, 28, 50, 1.18),          # forefeet
]
MARGIN_Y = 58


def make(src, dst):
    rgba = np.asarray(Image.open(src).convert('RGBA')).astype(float)
    # premultiply so the transparent surround cannot bleed into the edges
    rgba[..., :3] *= rgba[..., 3:] / 255
    h, w = rgba.shape[:2]
    W, H = int(X_RAT[-1]), h + 2 * MARGIN_Y
    centre = AXIS + MARGIN_Y

    dy, dx = np.mgrid[:H, :W].astype(float)
    sx = np.interp(dx, X_RAT, X_MOUSE)
    table = ndimage.gaussian_filter1d(np.interp(np.arange(w), Y_AT, Y_SCALE), 14, mode='nearest')
    sy = AXIS + (dy - centre) / table[np.clip(np.round(sx).astype(int), 0, w - 1)]
    for cx, cy, a, end, size in FEATURES:
        ox, oy = sx - cx, sy - cy
        r = np.hypot(ox, oy)
        inner = a * size
        new = np.where(r <= inner, r / size, a + (r - inner) * (end - a) / (end - inner))
        scale = np.where((r > 1e-6) & (r < end), new / np.maximum(r, 1e-6), 1.0)
        sx, sy = cx + ox * scale, cy + oy * scale

    out = np.stack([ndimage.map_coordinates(rgba[..., c], [sy, sx], order=1, mode='constant') for c in range(4)], -1)
    alpha = out[..., 3:]
    out[..., :3] = np.where(alpha > 0, out[..., :3] * 255 / np.maximum(alpha, 1e-3), 0)
    Image.fromarray(np.clip(out, 0, 255).round().astype('uint8'), 'RGBA').save(dst, quality=92, alpha_quality=100, method=6)

    rump, nose = np.interp([RUMP, NOSE], X_MOUSE, X_RAT)
    ppu = (nose - rump) / (27.9 + 23.1)                         # the old rat's rump and nose, in sprite units
    x0, y0 = -23.1 - rump / ppu, -centre / ppu
    print('wrote', dst, (W, H), 'box', [round(float(v), 2) for v in (x0, y0, x0 + W / ppu, y0 + H / ppu)])


if __name__ == '__main__':
    make(sys.argv[1], sys.argv[2])
