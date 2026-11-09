"""Cut the white rabbit render into the layers the rabbit scenes animate.

The render comes with a rough cut-out: its edge is blocky and it keeps a patch of floor
around the front paws. This smooths the edge, removes the floor along a hand-traced line,
and takes the colour from the sharper full render. It then splits the animal into a body
without ears, one layer for each ear so they can move, and a head that can stand alone.
The layers overlap at the ear roots, so stacked together they rebuild the render exactly.

    python tools/animal-sprites/cut_rabbit.py <render.jpg> <cutout.webp> static/assets/img/animals

Prints the sprite boxes to use in animal-art.js. Needs Pillow, numpy and scipy.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ORIGIN = (514, 450)                                     # midway between the eyes; source pixels are scene units
# Floor under and between the feet, left to right along the paws, in source pixels
FLOOR = [
    (250, 876), (299, 876), (307, 885), (320, 893), (335, 897.5), (352, 897), (370, 894.5), (385, 891), (392, 889),
    (389, 907), (381, 925), (381, 940), (384, 950), (391, 958), (410, 966), (440, 972.5), (462, 971), (475, 965), (480, 952),
    (479, 935), (484, 915), (485, 895), (483, 875), (480, 855), (482, 845), (492, 840), (505, 837), (520, 837), (535, 839),
    (548, 843), (554, 851), (553, 870), (550, 890), (548, 908), (552, 930), (556, 945), (553, 958), (565, 965), (580, 969.5),
    (600, 969.5), (627, 961), (646, 948), (645, 930), (644, 907), (641, 897), (650, 896.5), (665, 897), (680, 891), (700, 882),
    (708, 878), (760, 876), (760, 1000), (250, 1000),
]
# Where each ear joins the head: inner end, outer end, and a point out on the ear
EARS = {'rbEarL': ((497, 318), (405, 410), (380, 250)), 'rbEarR': ((533, 316), (618, 412), (650, 220))}
HEAD = (514, 510, 112, 190)                             # centre x, y and half width, height of the stand-alone head


def smooth(a, lo, hi):
    t = np.clip((a - lo) / (hi - lo), 0, 1)
    return t * t * (3 - 2 * t)


def ear_side(xx, yy, inner, outer, on_ear):
    """Signed distance from the ear root, positive on the ear, and nothing below the root."""
    (px, py), (qx, qy) = inner, outer
    nx, ny = qy - py, px - qx
    n = np.hypot(nx, ny)
    nx, ny = nx / n, ny / n
    if (on_ear[0] - px) * nx + (on_ear[1] - py) * ny < 0:
        nx, ny = -nx, -ny
    d = (xx - px) * nx + (yy - py) * ny
    other_side = (xx > ORIGIN[0]) if on_ear[0] < ORIGIN[0] else (xx < ORIGIN[0])
    return np.where((yy > 420) | other_side, -99.0, d)


def save(rgb, alpha, name, out):
    a = (np.clip(alpha, 0, 1) * 255).round().astype(np.uint8)
    ys, xs = np.where(a > 0)
    x0, y0, x1, y1 = max(xs.min() - 2, 0), max(ys.min() - 2, 0), min(xs.max() + 3, a.shape[1]), min(ys.max() + 3, a.shape[0])
    # colour under the clear area copies the nearest fur, so no fringe shows when the browser scales it
    far = ndimage.distance_transform_edt(a == 0, return_distances=False, return_indices=True)
    filled = rgb[far[0], far[1]]
    Image.fromarray(np.dstack((filled, a))[y0:y1, x0:x1], 'RGBA').save(os.path.join(out, name + '.webp'), quality=90, method=6)
    print(f"{name}: [{x0 - ORIGIN[0]}, {y0 - ORIGIN[1]}, {x1 - ORIGIN[0]}, {y1 - ORIGIN[1]}]")


def main(render, cutout, out):
    rgb = np.array(Image.open(render).convert('RGB'))
    h, w = rgb.shape[:2]
    matte = Image.fromarray(np.array(Image.open(cutout).convert('RGBA'))[..., 3])
    ImageDraw.Draw(matte).polygon(FLOOR, fill=0)
    a = ndimage.gaussian_filter(np.array(matte, float) / 255, 2.6)
    a = ndimage.gaussian_filter(smooth(a, .42, .62), .8)

    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    body = a.copy()
    for name, (inner, outer, on_ear) in EARS.items():
        d = ear_side(xx, yy, inner, outer, on_ear)
        save(rgb, a * smooth(d, -10, -2) * (1 - smooth(yy, 402, 418)), name, out)
        body *= 1 - smooth(d, -2, 8)
    save(rgb, body, 'rbBody', out)

    # an irregular edge reads as fur where the head has to stand alone
    fur = ndimage.gaussian_filter(np.random.default_rng(7).normal(size=(h, w)), 2.2)
    fur = fur / fur.std() * .009
    cx, cy, rx, ry = HEAD
    # taller above the centre, so the top of the skull is bounded by the animal's own outline
    r = np.hypot((xx - cx) / rx, (yy - cy) / np.where(yy < cy, ry * 1.14, ry)) + fur
    save(rgb, body * (1 - smooth(r, .93, 1)), 'rbHead', out)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
