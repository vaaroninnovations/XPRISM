"""Bake the "before" plates for the frog dissection stations (Exp 07 and Exp 12).

Two of the supplied renders show a stage that the student has not reached yet:
the pinned frog already has its pins, and the opened oesophagus already has its
flap pins, purple START/FINISH lines and poppy seeds. The stations need the frog
without them, so the student's own actions can put them there.

This paints those details out and writes new files beside the originals, which
are left untouched:

    frog-ventral-pinned-3d.jpg                -> frog-ventral-unpinned-3d.webp
    frog-oesophagus-ciliary-dissection-3d.jpg -> frog-oesophagus-unmarked-3d.webp

Run from the repository root (needs Pillow, numpy, scipy):
    python tools/frog-plates/clean_plates.py
"""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

FROG = Path(__file__).resolve().parents[2] / 'static' / 'assets' / 'img' / 'frog'

# ---------------------------------------------------------------- what to remove (source pixels)
# (x, y, r): pin heads.  (x1, y1, x2, y2): pin shafts, including the parts seen through the webs.
VENTRAL_HEADS = [(428, 142, 12), (501, 170, 12), (864, 165, 12), (933, 141, 12),
                 (268, 495, 15), (322, 485, 15), (405, 503, 15), (962, 514, 15), (1053, 471, 15), (1111, 498, 15)]
VENTRAL_SHAFTS = [
    (431, 151, 434, 170), (440, 234, 422, 277), (497, 180, 478, 222), (460, 259, 449, 285),   # forelimb, viewer's left
    (869, 174, 889, 220), (909, 261, 924, 290), (930, 151, 929, 176), (929, 235, 946, 276),   # forelimb, viewer's right
    (270, 507, 281, 554), (289, 600, 303, 660), (323, 496, 326, 539), (326, 565, 328, 597),   # hind foot, viewer's left
    (402, 516, 398, 548), (394, 572, 392, 586), (384, 624, 379, 666),
    (963, 526, 965, 558), (967, 580, 968, 595), (972, 644, 975, 670),                         # hind foot, viewer's right
    (1053, 484, 1053, 538), (1052, 564, 1052, 598), (1106, 510, 1089, 555), (1064, 611, 1047, 652),
]
OESO_HEADS = [(369, 219, 8), (301, 312, 9), (296, 417, 9), (275, 500, 10),
              (857, 225, 8), (879, 314, 7), (927, 309, 9), (916, 421, 9), (925, 501, 10)]
OESO_SHAFTS = [
    (369, 219, 405, 320), (301, 312, 365, 418), (296, 417, 350, 488), (275, 500, 368, 512),
    (857, 225, 815, 329), (879, 314, 851, 362), (927, 309, 860, 417), (916, 421, 858, 492), (925, 501, 838, 511),
    (879, 316, 843, 344),                                                                      # stray white wire by the upper-right pin
]
OESO_BLOBS = [(893, 299, 898, 288, 878, 312, 9)]                                               # stray black-handled probe tip
# centre lines of the two purple marks
START_LINE = [(377, 379), (420, 375), (470, 379), (500, 384), (545, 391), (575, 406), (620, 406), (650, 394), (695, 384), (740, 377), (800, 373), (840, 384)]
FINISH_LINE = [(362, 472), (425, 469), (470, 475), (530, 479), (572, 496), (620, 496), (670, 479), (735, 470), (800, 468), (843, 479)]
SEEDS = (605, 447, 40, 46)                                                                     # cx, cy, rx, ry of the poppy-seed cloud


def disc(mask, x, y, r):
    yy, xx = np.ogrid[:mask.shape[0], :mask.shape[1]]
    mask[(xx - x) ** 2 + (yy - y) ** 2 <= r * r] = True


def capsule(mask, x1, y1, x2, y2, r):
    yy, xx = np.mgrid[:mask.shape[0], :mask.shape[1]]
    dx, dy = x2 - x1, y2 - y1
    t = np.clip(((xx - x1) * dx + (yy - y1) * dy) / max(dx * dx + dy * dy, 1), 0, 1)
    mask[(xx - x1 - t * dx) ** 2 + (yy - y1 - t * dy) ** 2 <= r * r] = True


def heal(rgb, mask, sigma=1.6):
    """Fill the holes from their surroundings, then borrow grain from nearby clean pixels."""
    out = rgb.copy()
    near = ndimage.distance_transform_edt(mask, return_distances=False, return_indices=True)
    fill = rgb[near[0], near[1]]
    soft = np.stack([ndimage.gaussian_filter(fill[..., c], sigma) for c in range(3)], -1)
    grain = rgb - np.stack([ndimage.gaussian_filter(rgb[..., c], 2.2) for c in range(3)], -1)
    labels, n = ndimage.label(mask, structure=np.ones((3, 3)))
    for i, sl in enumerate(ndimage.find_objects(labels), 1):
        hole = labels[sl] == i
        if hole.sum() < 120:                                                # slivers need no grain
            continue
        reach, tone = max(hole.shape) + 8, soft[sl][hole].mean(0)
        for ang in np.linspace(0, 2 * np.pi, 24, endpoint=False):
            dy, dx = int(round(np.sin(ang) * reach)), int(round(np.cos(ang) * reach))
            y0, y1, x0, x1 = sl[0].start + dy, sl[0].stop + dy, sl[1].start + dx, sl[1].stop + dx
            if y0 < 0 or x0 < 0 or y1 > mask.shape[0] or x1 > mask.shape[1] or mask[y0:y1, x0:x1].any():
                continue
            if np.abs(rgb[y0:y1, x0:x1][hole].mean(0) - tone).max() < 14:       # only borrow from matching material
                soft[sl][hole] += grain[y0:y1, x0:x1][hole] * 0.7
                break
    alpha = ndimage.gaussian_filter(ndimage.binary_dilation(mask, iterations=1).astype(float), 0.9)
    alpha[mask] = 1
    return out * (1 - alpha[..., None]) + soft * alpha[..., None]


def load(name):
    return np.asarray(Image.open(FROG / name).convert('RGB')).astype(float)


def save(rgb, name):
    Image.fromarray(np.clip(rgb, 0, 255).astype('uint8')).save(FROG / name, quality=90, method=6)
    print('wrote', name)


def ventral():
    rgb = load('frog-ventral-pinned-3d.jpg')
    mask = np.zeros(rgb.shape[:2], bool)
    for x, y, r in VENTRAL_HEADS:
        disc(mask, x, y, r)
    for seg in VENTRAL_SHAFTS:
        capsule(mask, *seg, 4.5)
    save(heal(rgb, mask), 'frog-ventral-unpinned-3d.webp')


def oesophagus():
    rgb = load('frog-oesophagus-ciliary-dissection-3d.jpg')
    h, w = rgb.shape[:2]
    pins = np.zeros((h, w), bool)
    for x, y, r in OESO_HEADS:
        disc(pins, x, y, r)
    for seg in OESO_SHAFTS:
        capsule(pins, *seg, 6)
    for x, y, x1, y1, x2, y2, r in OESO_BLOBS:
        capsule(pins, x1, y1, x2, y2, r)
    rgb = heal(rgb, pins)

    # the purple lines: anything purplish in a band along each measured line
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    band = np.zeros((h, w), bool)
    for line in (START_LINE, FINISH_LINE):
        for (x1, y1), (x2, y2) in zip(line, line[1:]):
            capsule(band, x1, y1, x2, y2, 11)
    purple = (b - g > 6) & (r - g > 0) & (b > r * 0.6) & band
    rgb = heal(rgb, ndimage.binary_dilation(purple, iterations=3), sigma=2.4)

    # the seeds: dark specks inside their cloud, judged against the wider mucosa
    cx, cy, rx, ry = SEEDS
    yy, xx = np.mgrid[:h, :w]
    cloud = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1
    lum = rgb.mean(-1)
    specks = ndimage.binary_dilation((lum < ndimage.median_filter(lum, size=91) - 12) & cloud, iterations=3)
    save(heal(rgb, specks, sigma=3.2), 'frog-oesophagus-unmarked-3d.webp')


if __name__ == '__main__':
    ventral()
    oesophagus()
