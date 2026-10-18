"""Shared scenery: small solid bases, tall foliage drawn in depth order."""
from __future__ import annotations

import math
import random

from blxverse.content.locations import HOMES, LOCATIONS


def _generate() -> list[dict]:
    rng = random.Random(90210)
    rects = [(loc['x'] - 40, loc['y'] - 40, loc['w'] + 80, loc['h'] + 100) for loc in LOCATIONS]
    rects += [(x - 40, y - 45, 172, 170) for x, y, _ in HOMES]
    out = []
    for _ in range(2500):
        x, y = rng.uniform(50, 1850), rng.uniform(100, 1220)
        if any(rx < x < rx + w and ry < y < ry + h for rx, ry, w, h in rects):
            continue
        # Keep the main promenade and venue entrances open.
        if abs(y - 640) < 56 or any(abs(x - v) < 35 for v in (175, 640, 1175, 1600)):
            continue
        if any(math.hypot(x - s['x'], y - s['y']) < 64 for s in out):
            continue
        bush = len(out) % 5 == 4
        out.append({'id': f'scenery_{len(out)}', 'kind': 'bush' if bush else 'tree',
                    'x': round(x, 1), 'y': round(y, 1), 'r': round(rng.uniform(20, 31), 1),
                    'hue': rng.random(), 'solid_radius': 12 if bush else 6})
        if len(out) == 74:
            break
    return out


SCENERY = _generate()
_BINS: dict[tuple[int, int], list[dict]] = {}
for _s in SCENERY:
    _BINS.setdefault((int(_s['x'] // 100), int(_s['y'] // 100)), []).append(_s)


def hits_scenery(x: float, y: float, radius: float) -> bool:
    bx, by = int(x // 100), int(y // 100)
    reach = math.ceil((radius + 12) / 100)
    for ix in range(bx - reach, bx + reach + 1):
        for iy in range(by - reach, by + reach + 1):
            for s in _BINS.get((ix, iy), ()):
                if (x - s['x']) ** 2 + (y - s['y']) ** 2 < (radius + s['solid_radius']) ** 2:
                    return True
    return False
