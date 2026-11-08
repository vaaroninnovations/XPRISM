"""Cut the top-view mouse render out of its studio backdrop.

The supplied render has an opaque pale plate and a ragged halo baked in around
the animal. That reads as a white blob on the maze floors and cages, so this
keeps only the mouse. White fur on a white plate cannot be split on colour, so
the outline against the plate is traced by hand; the pink parts are added back
on colour. The baked tail and whiskers are dropped because animalTopArt draws
its own, which can pose and animate. The picture is then trimmed to the animal.

    python tools/animal-sprites/cut_top_mouse.py <render.webp> static/assets/img/animals/top-mouse.webp

Needs Pillow, numpy and scipy.
"""
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

# Clockwise from the tail base, in source pixels. Across the top and round the snout the
# outline is deliberately loose, because the picture's own transparency bounds it there.
OUTLINE = [
    (216, 197), (228, 176), (244, 153), (262, 134), (282, 116), (305, 101), (330, 88),
    (350, 55), (700, 55), (780, 120), (830, 150), (888, 190), (888, 225), (850, 238), (817, 252), (800, 262),
    (760, 279), (738, 285), (722, 286), (716, 296), (700, 305), (684, 307), (670, 303), (660, 304), (640, 316),
    (627, 320), (600, 330), (573, 328), (540, 318), (500, 320), (460, 317), (433, 320), (427, 323), (413, 335),
    (380, 347), (360, 342), (340, 332), (320, 320), (300, 300), (280, 285), (258, 263), (240, 240), (222, 222),
    (218, 222), (213, 214), (213, 205),
]
TRIM = (205, 55, 890, 360)                                              # left, top, right, bottom of the saved picture


def cut(src, dst):
    rgba = np.asarray(Image.open(src).convert('RGBA')).astype(float)
    h, w = rgba.shape[:2]
    alpha = rgba[..., 3]
    sat = rgba[..., :3].max(-1) - rgba[..., :3].min(-1)

    drawn = Image.new('L', (w, h), 0)
    ImageDraw.Draw(drawn).polygon(OUTLINE, fill=255)
    keep = (np.asarray(drawn) > 0) & (alpha > 150)
    near = ndimage.binary_dilation(keep, iterations=45)
    keep |= (sat > 26) & (alpha > 120) & near                           # paws and ear rims outside the outline
    keep = ndimage.binary_opening(keep, iterations=2)                   # drops the whiskers
    labels, n = ndimage.label(keep, structure=np.ones((3, 3)))
    sizes = ndimage.sum(keep, labels, range(1, n + 1))
    keep = ndimage.binary_fill_holes(labels == 1 + int(np.argmax(sizes)))

    edge = np.clip((ndimage.gaussian_filter(keep.astype(float), 1.2) - 0.2) / 0.55, 0, 1)
    out = rgba.copy()
    out[..., 3] = np.minimum(alpha, 255 * edge)
    Image.fromarray(out.round().astype('uint8'), 'RGBA').crop(TRIM).save(dst, quality=92, alpha_quality=100, method=6)
    ys, xs = np.where(out[..., 3] > 8)
    print('wrote', dst, 'content', xs.min(), ys.min(), xs.max(), ys.max())


if __name__ == '__main__':
    cut(sys.argv[1], sys.argv[2])
