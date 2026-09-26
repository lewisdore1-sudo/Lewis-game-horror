"""Room identities, variants and furniture layouts.

Each East Wing slot shows one *identity* (Study, Bedroom, Gallery, Parlour) in
one *variant*:
  QUIET  – original arrangement, warm lamp light, no obvious threat
  WRONG  – the same room mirrored, chairs upside down, pictures inverted,
           clocks stopped at 3:00. Familiar space made unfamiliar.
  NIGHT  – lights dying and red, furniture knocked over, stains and writing
           on the walls. Something has been here.

Local room coordinates: lx 0..6 (west→east), ly 0..7 (door wall → back wall).
The door sits at lx 3, ly 0; the zone lx 2..4, ly 0..1.6 is always kept clear.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from .layout import AREAS, Rect

ROOM_W, ROOM_D = 6.0, 7.0
QUIET, WRONG, NIGHT = "quiet", "wrong", "night"
VARIANTS = (QUIET, WRONG, NIGHT)
IDENTITIES = ("study", "bedroom", "gallery", "parlour")

# key id -> (identity, variant) that holds it
KEY_HOMES = {
    "brass": ("study", QUIET),
    "bone": ("bedroom", NIGHT),
    "clock": ("gallery", WRONG),
}
KEY_NAMES = {"brass": "Brass Key", "bone": "Bone-White Key", "clock": "Clockwork Key"}

# kind -> (width along lx, depth along ly, height)
FOOTPRINT = {
    "desk": (1.6, 0.8, 0.78),
    "chair": (0.5, 0.5, 0.95),
    "armchair": (0.9, 0.9, 1.0),
    "bookshelf": (1.8, 0.4, 2.3),
    "bed": (1.9, 2.3, 0.6),
    "nightstand": (0.5, 0.45, 0.6),
    "wardrobe": (1.4, 0.65, 2.2),
    "dresser": (1.3, 0.5, 0.85),
    "globe": (0.6, 0.6, 1.1),
    "bench": (1.8, 0.5, 0.48),
    "clock": (0.6, 0.45, 2.2),
    "plinth": (0.6, 0.6, 1.1),
    "sofa": (2.2, 0.9, 0.85),
    "coffee_table": (1.2, 0.6, 0.45),
    "piano": (1.5, 0.65, 1.2),
    "floor_lamp": (0.4, 0.4, 1.7),
    "fireplace": (1.8, 0.5, 1.3),
    # non-colliding
    "rug": (2.6, 3.2, 0.01),
    "painting": (1.0, 0.05, 0.8),
    "writing": (2.0, 0.02, 0.6),
    "stain": (1.2, 1.2, 0.01),
    "desk_lamp": (0.25, 0.25, 0.45),
    "candle": (0.1, 0.1, 0.25),
    "book_pile": (0.4, 0.3, 0.25),
    "mirror": (0.8, 0.04, 1.2),
}
NON_COLLIDING = {"rug", "painting", "writing", "stain", "desk_lamp", "candle", "book_pile", "mirror"}

ROOM_STYLE = {
    #            wall material   lamp colour (r, g, b)
    "study":   ("wall_study",   (1.0, 0.78, 0.5)),
    "bedroom": ("wall_rose",    (1.0, 0.72, 0.55)),
    "gallery": ("wall_gallery", (1.0, 0.8, 0.62)),
    "parlour": ("wall_parlour", (1.0, 0.75, 0.45)),
}

NIGHT_WRITING = [
    "IT MOVES WHEN YOU DON'T LOOK",
    "YOU LEFT. IT CHANGED.",
    "COME BACK INSIDE",
    "DON'T TURN AROUND",
    "THE HOUSE REMEMBERS YOU",
    "WHO LET YOU LEAVE",
]


@dataclass
class Item:
    kind: str
    lx: float
    ly: float
    rot: int = 0                  # degrees, 0 = facing south (towards door)
    z: float = 0.0
    wall: str | None = None       # "n", "w", "e" for wall-mounted items
    flags: frozenset = frozenset()
    text: str | None = None
    art: int = 0                  # painting index

    @property
    def collides(self) -> bool:
        return self.kind not in NON_COLLIDING and self.wall is None

    def footprint(self) -> tuple[float, float]:
        w, d, _ = FOOTPRINT[self.kind]
        if self.rot % 180 == 90:
            w, d = d, w
        if "fallen" in self.flags:
            h = FOOTPRINT[self.kind][2]
            # knocked over: lies along its height
            w, d = (max(w, h * 0.9), d) if self.rot % 180 == 0 else (w, max(d, h * 0.9))
        return w, d


@dataclass
class KeySpec:
    key_id: str
    lx: float
    ly: float
    z: float


@dataclass
class RoomLayout:
    identity: str
    variant: str
    items: list[Item]
    key: KeySpec | None
    wall_mat: str
    lamp_color: tuple[float, float, float]
    lamp_power: float
    flicker: float                # 0 = steady, 1 = violent
    writing: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Base (QUIET) layouts
# --------------------------------------------------------------------------
def _base(identity: str) -> list[Item]:
    if identity == "study":
        return [
            Item("rug", 3.0, 3.6),
            Item("desk", 3.0, 5.9, rot=180),
            Item("chair", 3.0, 5.05, rot=180),
            Item("desk_lamp", 2.4, 5.95, z=0.78),
            Item("book_pile", 3.55, 5.8, z=0.78),
            Item("bookshelf", 0.25, 3.0, rot=90),
            Item("bookshelf", 0.25, 5.2, rot=90),
            Item("bookshelf", 5.75, 4.4, rot=270),
            Item("armchair", 5.1, 2.3, rot=270),
            Item("globe", 0.9, 1.3),
            Item("painting", 3.0, 7.0, wall="n", z=1.8, art=0),
            Item("painting", 6.0, 2.3, wall="e", z=1.7, art=1),
        ]
    if identity == "bedroom":
        return [
            Item("rug", 3.0, 3.0),
            Item("bed", 3.0, 5.75),
            Item("nightstand", 1.65, 6.6),
            Item("nightstand", 4.35, 6.6),
            Item("candle", 1.65, 6.6, z=0.6),
            Item("desk_lamp", 4.35, 6.6, z=0.6),
            Item("wardrobe", 0.35, 2.6, rot=90),
            Item("dresser", 5.7, 2.9, rot=270),
            Item("mirror", 6.0, 2.9, wall="e", z=1.6),
            Item("chair", 5.1, 1.2, rot=270),
            Item("painting", 3.0, 7.0, wall="n", z=2.2, art=2),
        ]
    if identity == "gallery":
        return [
            Item("bench", 3.0, 3.9),
            Item("clock", 5.5, 6.6, rot=0),
            Item("plinth", 1.1, 5.6),
            Item("plinth", 1.1, 2.6),
            Item("painting", 1.5, 7.0, wall="n", z=1.7, art=3),
            Item("painting", 3.6, 7.0, wall="n", z=1.7, art=4),
            Item("painting", 0.0, 2.2, wall="w", z=1.7, art=5),
            Item("painting", 0.0, 4.5, wall="w", z=1.7, art=6),
            Item("painting", 6.0, 2.2, wall="e", z=1.7, art=7),
            Item("painting", 6.0, 4.5, wall="e", z=1.7, art=0),
        ]
    if identity == "parlour":
        return [
            Item("rug", 3.0, 4.0),
            Item("sofa", 3.0, 6.3, rot=0),
            Item("coffee_table", 3.0, 4.5),
            Item("armchair", 1.3, 3.8, rot=90),
            Item("armchair", 4.7, 3.8, rot=270),
            Item("fireplace", 0.25, 5.6, rot=90),
            Item("piano", 5.6, 6.0, rot=270),
            Item("floor_lamp", 5.5, 1.2),
            Item("candle", 3.0, 4.5, z=0.45),
            Item("painting", 3.0, 7.0, wall="n", z=2.1, art=1),
        ]
    raise ValueError(identity)


def _mirror(it: Item) -> Item:
    wall = {"w": "e", "e": "w"}.get(it.wall, it.wall)
    rot = (360 - it.rot) % 360
    flags = set(it.flags)
    if it.kind == "chair":
        flags.add("upside")
    if it.kind == "painting":
        flags.add("inverted")
    if it.kind == "clock":
        flags.add("three_am")
    return replace(it, lx=ROOM_W - it.lx, wall=wall, rot=rot, flags=frozenset(flags))


def _night(it: Item, i: int) -> Item:
    flags = set(it.flags)
    if it.kind in ("chair", "floor_lamp", "desk_lamp") or (it.kind == "plinth" and i % 2 == 0):
        flags.add("fallen")
    if it.kind == "painting":
        flags.add("askew")
    if it.kind == "armchair" and i % 2:
        # turned to face the wall
        return replace(it, rot=(it.rot + 180) % 360, flags=frozenset(flags))
    return replace(it, flags=frozenset(flags))


WALL_CLEAR = 0.22          # inner wall face is 0.15 from the room edge
DOOR_ZONE = (1.9, 4.1, 1.75)   # lx0, lx1, ly max kept clear in front of the door


def _settle(it: Item) -> Item:
    """Keep colliding furniture inside the room and out of the doorway."""
    if not it.collides:
        return it
    w, d = it.footprint()
    lx = min(max(it.lx, WALL_CLEAR + w / 2), ROOM_W - WALL_CLEAR - w / 2)
    ly = min(max(it.ly, WALL_CLEAR + d / 2), ROOM_D - WALL_CLEAR - d / 2)
    x0, x1, ymax = DOOR_ZONE
    if lx + w / 2 > x0 and lx - w / 2 < x1 and ly - d / 2 < ymax:
        ly = ymax + d / 2 + 0.05
    return replace(it, lx=lx, ly=ly)


def room_layout(identity: str, variant: str, seed: int = 0) -> RoomLayout:
    wall_mat, lamp = ROOM_STYLE[identity]
    items = _base(identity)
    writing: list[str] = []
    power, flicker = 1.0, 0.05
    if variant == WRONG:
        items = [_mirror(it) for it in items]
        power, flicker = 0.75, 0.2
        lamp = (lamp[0] * 0.85, lamp[1], lamp[2] * 1.15)   # colder, off
    elif variant == NIGHT:
        items = [_night(it, i) for i, it in enumerate(items)]
        items.append(Item("stain", 2.2 + (seed % 3) * 0.5, 2.4))
        items.append(Item("stain", 4.2, 5.0 - (seed % 2) * 0.8))
        w1 = NIGHT_WRITING[seed % len(NIGHT_WRITING)]
        w2 = NIGHT_WRITING[(seed + 3) % len(NIGHT_WRITING)]
        items.append(Item("writing", 0.0, 3.8, wall="w", z=1.5, text=w1))
        items.append(Item("writing", 6.0, 5.2, wall="e", z=1.3, text=w2))
        writing = [w1, w2]
        lamp = (1.0, 0.18, 0.12)
        power, flicker = 0.55, 0.85
    items = [_settle(it) for it in items]
    key = None
    for key_id, (ident, var) in KEY_HOMES.items():
        if ident == identity and var == variant:
            if key_id == "brass":
                key = KeySpec(key_id, 3.25, 5.75, 0.8)          # on the desk
            elif key_id == "bone":
                key = KeySpec(key_id, 3.0, 6.25, 0.66)          # on the pillow
            elif key_id == "clock":
                key = KeySpec(key_id, 0.5, 6.2, 0.02)           # at the stopped clock (mirrored)
    return RoomLayout(identity, variant, items, key, wall_mat, lamp, power, flicker, writing)


def to_world(slot: str, lx: float, ly: float) -> tuple[float, float]:
    r = AREAS[slot].rect
    return r.x0 + lx, r.y0 + ly


def colliders(slot: str, layout: RoomLayout) -> list[Rect]:
    out = []
    for it in layout.items:
        if not it.collides:
            continue
        w, d = it.footprint()
        x, y = to_world(slot, it.lx, it.ly)
        out.append(Rect(x - w / 2, y - d / 2, x + w / 2, y + d / 2))
    return out


# --------------------------------------------------------------------------
# Grand Hall stages (the hall shifts every time a key is taken)
# --------------------------------------------------------------------------
HALL_STAGE_TEXT = [
    "The Grand Hall. Still, for now.",
    "The portraits have turned to face the east door.",
    "Every chair in the hall now faces the garden.",
    "The hall is darker. The chairs are gone. Only the portraits remain.",
]


def hall_items(stage: int) -> list[dict]:
    """Returns hall props in world coordinates. dict(kind, x, y, rot, flags)."""
    items: list[dict] = []
    chair_rot = 0
    if stage == 1:
        chair_rot = 90
    elif stage >= 2:
        chair_rot = 180     # facing north / the garden door
    if stage < 3:
        for i, y in enumerate((2.0, 4.0, 11.0)):
            for x in (-7.3, 7.3):
                flags = ("upside",) if stage == 2 and i == 1 else ()
                items.append(dict(kind="chair", x=x, y=y, rot=chair_rot, flags=flags))
    portrait_flags = ("turned",) if stage >= 1 else ()
    for x in (-5.0, 5.0):
        items.append(dict(kind="portrait", x=x, y=0.15, rot=0, flags=portrait_flags))
    for y in (3.0, 11.0):
        items.append(dict(kind="portrait", x=-7.85, y=y, rot=90, flags=portrait_flags))
    items.append(dict(kind="clock", x=-7.4, y=5.4, rot=90, flags=("three_am",) if stage >= 2 else ()))
    return items


def hall_colliders(stage: int) -> list[Rect]:
    out = []
    for it in hall_items(stage):
        if it["kind"] in ("chair", "clock"):
            w, d, _ = FOOTPRINT[it["kind"]]
            if it["rot"] % 180 == 90:
                w, d = d, w
            out.append(Rect(it["x"] - w / 2, it["y"] - d / 2, it["x"] + w / 2, it["y"] + d / 2))
    return out


HALL_NOTE = (
    "You came back. Good.\n\n"
    "The house has kept three keys for you in the East Wing.\n"
    "It will not hand them over while you watch.\n\n"
    "The study keeps its key while it is calm.\n"
    "The bedroom only gives when the lights die.\n"
    "In the gallery, wait until the clock is wrong.\n\n"
    "When you leave a room, it forgets you.\n"
    "When you look away, something remembers.\n\n"
    "Then water the orchid in the glasshouse.\n"
    "It is the only thing here still alive.\n\n"
    "                                   - M."
)
