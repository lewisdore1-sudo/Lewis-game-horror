"""2D collision and line-of-sight helpers (engine independent)."""
from __future__ import annotations

import math
from typing import Iterable

from .layout import Rect


def _overlaps(x: float, y: float, r: float, rect: Rect) -> bool:
    return (rect.x0 - r < x < rect.x1 + r) and (rect.y0 - r < y < rect.y1 + r)


def move_and_collide(x: float, y: float, dx: float, dy: float, r: float,
                     rects: Iterable[Rect]) -> tuple[float, float]:
    """Move a square body of half-size r, sliding along axis-aligned rects.

    Resolves X then Y so the body slides along walls instead of sticking.
    Large moves are sub-stepped so thin walls can't be tunnelled through.
    """
    rects = list(rects)
    dist = math.hypot(dx, dy)
    steps = max(1, int(math.ceil(dist / (r * 0.8))))
    sx, sy = dx / steps, dy / steps
    for _ in range(steps):
        nx = x + sx
        for rc in rects:
            if _overlaps(nx, y, r, rc):
                nx = (rc.x0 - r - 1e-4) if sx > 0 else (rc.x1 + r + 1e-4) if sx < 0 else nx
        x = nx
        ny = y + sy
        for rc in rects:
            if _overlaps(x, ny, r, rc):
                ny = (rc.y0 - r - 1e-4) if sy > 0 else (rc.y1 + r + 1e-4) if sy < 0 else ny
        y = ny
    return x, y


def point_free(x: float, y: float, r: float, rects: Iterable[Rect]) -> bool:
    return not any(_overlaps(x, y, r, rc) for rc in rects)


def segment_hits_rect(ax: float, ay: float, bx: float, by: float, rc: Rect) -> bool:
    """Liang–Barsky style slab test: does segment A→B pass through rect?"""
    dx, dy = bx - ax, by - ay
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, ax - rc.x0), (dx, rc.x1 - ax), (-dy, ay - rc.y0), (dy, rc.y1 - ay)):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                if t > t1:
                    return False
                t0 = max(t0, t)
            else:
                if t < t0:
                    return False
                t1 = min(t1, t)
    return t0 <= t1


def line_clear(ax: float, ay: float, bx: float, by: float, rects: Iterable[Rect]) -> bool:
    return not any(segment_hits_rect(ax, ay, bx, by, rc) for rc in rects)


def forward_2d(heading_deg: float) -> tuple[float, float]:
    """Panda3D heading: 0 looks +Y (north), positive turns left (counter-clockwise)."""
    h = math.radians(heading_deg)
    return -math.sin(h), math.cos(h)


def angle_to(from_x, from_y, heading_deg, to_x, to_y) -> float:
    """Unsigned angle (degrees) between view direction and the target."""
    fx, fy = forward_2d(heading_deg)
    vx, vy = to_x - from_x, to_y - from_y
    d = math.hypot(vx, vy)
    if d < 1e-6:
        return 0.0
    dot = max(-1.0, min(1.0, (fx * vx + fy * vy) / d))
    return math.degrees(math.acos(dot))
