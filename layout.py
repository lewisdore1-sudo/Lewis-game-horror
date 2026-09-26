"""World layout for The Shifting Mansion.

Pure Python — no engine imports — so it can be unit-tested anywhere.

Coordinate system (matches Panda3D): X = east, Y = north, Z = up. Metres.

          GARDEN  (x -22..22, y 16..50, open sky, hedges)
            [ GLASSHOUSE x -7..7, y 32..44 ]
   --------------+ N door +----------------+---------+---------+
   |                                       | ROOM A  | ROOM B  | ROOM C  |
   W door    GRAND HALL (x -8..8, y 0..16)  E door  corridor (x 8..32, y 6.5..9)
   |                                       +---------+---------+---------+
   --------------+ FRONT DOOR (exit) +------
"""
from __future__ import annotations

from dataclasses import dataclass, field

WALL_T = 0.3          # wall thickness
DOOR_H = 2.5          # doorway height
HALL_H = 7.0          # grand hall ceiling
WING_H = 3.6          # east wing ceiling
GLASS_H = 4.2         # glasshouse wall height
HEDGE_H = 3.4
EYE_H = 1.65
PLAYER_R = 0.3


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    def contains(self, x: float, y: float, pad: float = 0.0) -> bool:
        return (self.x0 - pad <= x <= self.x1 + pad) and (self.y0 - pad <= y <= self.y1 + pad)

    def expanded(self, r: float) -> "Rect":
        return Rect(self.x0 - r, self.y0 - r, self.x1 + r, self.y1 + r)

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    def intersects(self, o: "Rect") -> bool:
        return self.x0 < o.x1 and o.x0 < self.x1 and self.y0 < o.y1 and o.y0 < self.y1


@dataclass
class Wall:
    """A vertical slab. mat_a faces -axis (south/west), mat_b faces +axis."""
    rect: Rect
    z0: float
    z1: float
    mat_a: str
    mat_b: str
    area: str
    solid: bool = True          # False for lintels above doors
    axis: str = "x"             # "x" = runs east-west, "y" = runs north-south


@dataclass
class Area:
    name: str
    rect: Rect
    height: float | None        # None = open sky
    floor_mat: str
    label: str


@dataclass
class Door:
    """A doorway that can block movement while locked."""
    name: str
    rect: Rect                  # collider while locked
    axis: str
    locked: bool = True
    label: str = ""


# --------------------------------------------------------------------------
# Areas
# --------------------------------------------------------------------------
AREAS: dict[str, Area] = {
    "hall": Area("hall", Rect(-8, 0, 8, 16), HALL_H, "marble", "The Grand Hall"),
    "corridor": Area("corridor", Rect(8, 6.5, 32, 9.0), WING_H, "carpet", "East Wing"),
    "room_a": Area("room_a", Rect(10, 9, 16, 16), WING_H, "wood", "East Wing"),
    "room_b": Area("room_b", Rect(18, 9, 24, 16), WING_H, "wood", "East Wing"),
    "room_c": Area("room_c", Rect(26, 9, 32, 16), WING_H, "wood", "East Wing"),
    "garden": Area("garden", Rect(-22, 16, 22, 50), None, "grass", "Botanical Garden"),
    "glasshouse": Area("glasshouse", Rect(-7, 32, 7, 44), GLASS_H, "tile", "The Glasshouse"),
}

ROOM_SLOTS = ("room_a", "room_b", "room_c")
# Door centre (x) of each room on the corridor's north wall (y = 9)
ROOM_DOOR_X = {"room_a": 13.0, "room_b": 21.0, "room_c": 29.0}
ROOM_DOOR_HALF = 0.65


def area_at(x: float, y: float) -> str | None:
    """Most specific area containing the point (glasshouse before garden)."""
    for name in ("glasshouse", "room_a", "room_b", "room_c", "corridor", "hall", "garden"):
        if AREAS[name].rect.contains(x, y):
            return name
    return None


# --------------------------------------------------------------------------
# Wall builders
# --------------------------------------------------------------------------
def _gaps_to_segments(a: float, b: float, gaps: list[tuple[float, float]]):
    segs, solid_from = [], a
    for g0, g1 in sorted(gaps):
        if g0 > solid_from:
            segs.append((solid_from, g0, True))
        segs.append((g0, g1, False))
        solid_from = g1
    if solid_from < b:
        segs.append((solid_from, b, True))
    return segs


def hwall(y, x0, x1, gaps, h, mat_a, mat_b, area, door_h=DOOR_H):
    """Wall running east-west at y. mat_a = south face, mat_b = north face."""
    out = []
    t = WALL_T / 2
    for a, b, solid in _gaps_to_segments(x0, x1, gaps):
        r = Rect(a, y - t, b, y + t)
        if solid:
            out.append(Wall(r, 0, h, mat_a, mat_b, area, True, "x"))
        elif h > door_h:
            out.append(Wall(r, door_h, h, mat_a, mat_b, area, False, "x"))
    return out


def vwall(x, y0, y1, gaps, h, mat_a, mat_b, area, door_h=DOOR_H):
    """Wall running north-south at x. mat_a = west face, mat_b = east face."""
    out = []
    t = WALL_T / 2
    for a, b, solid in _gaps_to_segments(y0, y1, gaps):
        r = Rect(x - t, a, x + t, b)
        if solid:
            out.append(Wall(r, 0, h, mat_a, mat_b, area, True, "y"))
        elif h > door_h:
            out.append(Wall(r, door_h, h, mat_a, mat_b, area, False, "y"))
    return out


def build_walls() -> list[Wall]:
    W: list[Wall] = []
    e = WALL_T / 2
    # Grand hall -------------------------------------------------------------
    W += hwall(0, -8 - e, 8 + e, [(-1.2, 1.2)], HALL_H, "stone", "damask", "hall", door_h=3.6)
    W += hwall(16, -8 - e, 8 + e, [(-1.2, 1.2)], HALL_H, "damask", "stone", "hall", door_h=3.6)
    W += vwall(8, 0, 16, [(6.5, 9.0)], HALL_H, "damask", "stone", "hall", door_h=3.0)
    W += vwall(-8, 0, 16, [(6.5, 9.0)], HALL_H, "stone", "damask", "hall", door_h=3.0)
    # East wing corridor ------------------------------------------------------
    W += hwall(6.5, 8 + e, 32 + e, [], WING_H, "stone", "panel", "corridor")
    door_gaps = [(cx - ROOM_DOOR_HALF, cx + ROOM_DOOR_HALF) for cx in ROOM_DOOR_X.values()]
    W += hwall(9.0, 8 + e, 32 + e, door_gaps, WING_H, "panel", "room", "corridor")
    W += vwall(32, 6.5, 9.0, [], WING_H, "panel", "stone", "corridor")
    # Rooms (walls use "room" material, swapped by shifting at render time) ---
    for slot in ROOM_SLOTS:
        r = AREAS[slot].rect
        W += hwall(16, r.x0 - e, r.x1 + e, [], WING_H, "room", "stone", slot)
        W += vwall(r.x0, 9 + e, 16 - e, [], WING_H, "stone", "room", slot)
        W += vwall(r.x1, 9 + e, 16 - e, [], WING_H, "room", "stone", slot)
    # Solid masonry between rooms (flush with the rooms' north walls)
    for fx0, fx1 in ((8 + e, 10 - e), (16 + e, 18 - e), (24 + e, 26 - e)):
        W.append(Wall(Rect(fx0, 9 + e, fx1, 16 + e), 0, WING_H, "stone", "stone", "corridor", True, "x"))
    # Garden boundary ----------------------------------------------------------
    W += vwall(-22, 16, 50, [], HEDGE_H, "hedge", "hedge", "garden")
    W += vwall(22, 16, 50, [], HEDGE_H, "hedge", "hedge", "garden")
    W += hwall(50, -22, 22, [], HEDGE_H, "hedge", "hedge", "garden")
    W += hwall(16, -22, -8 - e, [], HEDGE_H, "stone", "hedge", "garden")
    # Glasshouse ---------------------------------------------------------------
    W += hwall(32, -7, 7, [(-1.1, 1.1)], GLASS_H, "glass", "glass", "glasshouse", door_h=2.6)
    W += hwall(44, -7, 7, [], GLASS_H, "glass", "glass", "glasshouse")
    W += vwall(-7, 32, 44, [], GLASS_H, "glass", "glass", "glasshouse")
    W += vwall(7, 32, 44, [], GLASS_H, "glass", "glass", "glasshouse")
    return W


WALLS: list[Wall] = build_walls()

DOORS: dict[str, Door] = {
    "front": Door("front", Rect(-1.2, -0.15, 1.2, 0.15), "x", True, "The front door"),
    "west": Door("west", Rect(-8.15, 6.5, -7.85, 9.0), "y", True, "West Wing"),
}

# Static garden / hall obstacles (x0, y0, x1, y1) — furniture colliders are
# provided separately by rooms_data and change when rooms shift.
STATIC_OBSTACLES: dict[str, Rect] = {
    "fountain": Rect(-1.7, 22.3, 1.7, 25.7),
    "hall_table": Rect(-1.6, 7.0, 1.6, 9.0),
    "stair_left": Rect(-7.8, 12.5, -4.5, 15.8),
    "stair_right": Rect(4.5, 12.5, 7.8, 15.8),
    "plinth": Rect(-0.5, 39.5, 0.5, 40.5),
    "bench_w": Rect(-6.0, 26.5, -4.0, 27.2),
    "bench_e": Rect(4.0, 26.5, 6.0, 27.2),
    "tree_1": Rect(-15.4, 21.6, -14.6, 22.4),
    "tree_2": Rect(14.6, 21.6, 15.4, 22.4),
    "tree_3": Rect(-16.4, 38.6, -15.6, 39.4),
    "tree_4": Rect(15.6, 36.6, 16.4, 37.4),
    "tree_5": Rect(-10.4, 46.6, -9.6, 47.4),
    "tree_6": Rect(10.6, 45.6, 11.4, 46.4),
    "shed": Rect(-20.5, 44.0, -16.5, 48.5),
}

TREE_POSITIONS = [(-15, 22), (15, 22), (-16, 39), (16, 37), (-10, 47), (11, 46)]

PLAYER_START = (0.0, 3.0, 0.0)   # x, y, heading (degrees, 0 = north)


def solid_rects(extra: list[Rect] | None = None, include_locked_doors: bool = True) -> list[Rect]:
    rects = [w.rect for w in WALLS if w.solid]
    rects += list(STATIC_OBSTACLES.values())
    if include_locked_doors:
        rects += [d.rect for d in DOORS.values() if d.locked]
    if extra:
        rects += extra
    return rects


def sight_rects() -> list[Rect]:
    """Rects that block line of sight: solid walls and locked doors. Glass is see-through."""
    rects = [w.rect for w in WALLS if w.solid and w.mat_a != "glass"]
    rects += [d.rect for d in DOORS.values() if d.locked]
    return rects
