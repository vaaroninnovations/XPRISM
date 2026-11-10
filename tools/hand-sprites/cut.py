"""Cut the blue nitrile gloves out of the hand renders, for the benches that show an animal being held.

The renders show a gloved hand holding a white rat on a pale background. The benches draw their own
animals, so only the glove is kept: it is the one strongly blue thing in each picture, and is picked
out by colour. Fur and whiskers lying across a finger leave hairline gaps, which are closed.

    python tools/hand-sprites/cut.py tools/hand-sprites/renders static/assets/img/hands

Reads a.png (scruff), b.png (holding upright) and d.png (hanging by the tail); writes scruff.webp, hold.webp and
tail.webp, and prints each sprite's size and where it sat in its render.
Needs Pillow, numpy and scipy.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
LONG_SIDE = 640          # the hands are drawn 60 to 200 px wide on a 1000 px bench, shown at up to 2x


def glove_mask(rgb, bridge=0):
    r, g, b = (rgb[..., i].astype(np.int16) for i in range(3))
    mask = (b - r > 45) & (b - g > 12) & (b > 90)
    mask = ndi.binary_closing(mask, iterations=4)             # hairs across the glove
    mask = ndi.binary_fill_holes(mask)
    mask = ndi.binary_opening(mask, iterations=2)             # stray blue pixels in shadows
    if bridge:                                                # something held in the fist splits the glove: keep that part of the photo
        joined = ndi.binary_fill_holes(ndi.binary_erosion(ndi.binary_dilation(mask, iterations=bridge), iterations=bridge))
        coloured = rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2) > 22          # the held thing, not the grey backdrop
        mask = mask | (joined & ndi.binary_opening(coloured, iterations=2))
    return mask


def pieces(mask, min_share=0.004):
    lab, n = ndi.label(mask)
    sizes = ndi.sum(mask, lab, range(1, n + 1))
    keep = [i + 1 for i, s in enumerate(sizes) if s > mask.size * min_share]
    return lab, keep


def save(name, rgb, mask, fade=None, over=0.16):
    ys, xs = np.where(mask)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    alpha = ndi.gaussian_filter(mask[y0:y1, x0:x1].astype(np.float32), 1.2)
    alpha = np.clip((alpha - 0.35) / 0.5, 0, 1)                # a soft edge that sits just inside the glove
    if fade:                                                   # the render stops at the wrist: let it fade out, not end in a straight cut
        ramp = np.clip(np.arange(alpha.shape[1]) / (alpha.shape[1] * over), 0, 1) ** 1.5
        alpha *= ramp if fade == 'left' else ramp[::-1]
    cut = np.dstack([rgb[y0:y1, x0:x1], (alpha * 255).astype(np.uint8)])
    im = Image.fromarray(cut, 'RGBA')
    k = LONG_SIDE / max(im.size)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    im.save(OUT / f'{name}.webp', quality=88, method=6)
    print(f'{name}.webp  {im.width}x{im.height}  from x {x0}-{x1}, y {y0}-{y1} of {rgb.shape[1]}x{rgb.shape[0]}')


def load(name, bridge=0):
    rgb = np.asarray(Image.open(SRC / f'{name}.png').convert('RGB'))
    mask = glove_mask(rgb, bridge)
    lab, keep = pieces(mask)
    centres = {i: ndi.center_of_mass(mask, lab, i) for i in keep}      # (y, x)
    return rgb, lab, keep, centres


# a: the pinching hand comes in from the upper right; the hand under the chin is left out
rgb, lab, keep, c = load('a')
save('scruff', rgb, lab == min(keep, key=lambda i: c[i][0]), fade='right')

# b: two hands. Only the upper one is used: it holds the chest, and its fingers and thumb are separate pieces
# because the palm is behind the rat. The hand at the tail base would hide the paw the bench measures.
rgb, lab, keep, c = load('b')
middle = rgb.shape[0] * 0.58
save('hold', rgb, np.isin(lab, [i for i in keep if c[i][0] < middle]), fade='right', over=0.2)

# d: a fist with the tail running through it. The stretch of tail that crosses the fingers stays in the sprite,
# so the bench only has to bring its own tail up to the bottom of the fist.
rgb, lab, keep, c = load('d', bridge=30)
save('tail', rgb, lab == max(keep, key=lambda i: (lab == i).sum()), fade='left', over=0.08)
