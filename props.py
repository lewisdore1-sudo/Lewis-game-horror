"""Furniture and prop geometry, built in local space.

Convention: origin at the centre of the item's footprint, floor at z = 0,
front of the item facing -Y (south). The caller rotates it into place.
"""
from __future__ import annotations

import math

from .geom import MeshSet
from .rooms_data import FOOTPRINT


def _legs(m, w, d, h, t=0.05, inset=0.04):
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (w / 2 - inset - t / 2), sy * (d / 2 - inset - t / 2)
            m.box(x - t / 2, y - t / 2, 0, x + t / 2, y + t / 2, h, tile=0.5)


def desk(ms: MeshSet):
    w, d, h = FOOTPRINT["desk"]
    wd = ms["wood_dark"]
    wd.box(-w / 2, -d / 2, h - 0.05, w / 2, d / 2, h, tile=1.0)
    _legs(wd, w, d, h - 0.05, 0.06)
    # drawer pedestal + modesty panel
    wd.box(w / 2 - 0.45, -d / 2 + 0.04, 0.05, w / 2 - 0.05, d / 2 - 0.04, h - 0.05, tile=1.0)
    wd.box(-w / 2 + 0.06, d / 2 - 0.06, 0.25, w / 2 - 0.45, d / 2 - 0.03, h - 0.05, tile=1.0)
    for z in (0.18, 0.42):
        ms["brass"].box(w / 2 - 0.3, -d / 2 + 0.02, z + 0.1, w / 2 - 0.2, -d / 2 + 0.04, z + 0.13)
    ms["fabric_green"].box(-w / 2 + 0.2, -d / 2 + 0.15, h, w / 2 - 0.2, d / 2 - 0.15, h + 0.004, tile=0.6)


def chair(ms: MeshSet):
    w, d, h = FOOTPRINT["chair"]
    wd = ms["wood_dark"]
    seat = 0.46
    _legs(wd, w, d, seat - 0.04, 0.04, 0.02)
    ms["fabric_red"].box(-w / 2, -d / 2, seat - 0.05, w / 2, d / 2, seat + 0.02, tile=0.5)
    # back (at +Y so the chair faces -Y)
    for x in (-w / 2 + 0.02, w / 2 - 0.06):
        wd.box(x, d / 2 - 0.06, seat, x + 0.04, d / 2 - 0.02, h, tile=0.5)
    wd.box(-w / 2 + 0.02, d / 2 - 0.06, h - 0.12, w / 2 - 0.02, d / 2 - 0.02, h, tile=0.5)
    for i in range(3):
        x = -0.12 + i * 0.12
        wd.box(x - 0.015, d / 2 - 0.055, seat + 0.05, x + 0.015, d / 2 - 0.025, h - 0.12, tile=0.5)


def armchair(ms: MeshSet):
    w, d, h = FOOTPRINT["armchair"]
    f = ms["fabric_red"]
    f.box(-w / 2 + 0.12, -d / 2, 0.12, w / 2 - 0.12, d / 2 - 0.15, 0.45, tile=0.6)
    f.box(-w / 2, -d / 2, 0.12, -w / 2 + 0.14, d / 2, 0.66, tile=0.6)
    f.box(w / 2 - 0.14, -d / 2, 0.12, w / 2, d / 2, 0.66, tile=0.6)
    f.box(-w / 2, d / 2 - 0.2, 0.12, w / 2, d / 2, h, tile=0.6)
    ms["wood_dark"].box(-w / 2 + 0.02, -d / 2 + 0.02, 0, w / 2 - 0.02, d / 2 - 0.02, 0.12, tile=0.6)


def sofa(ms: MeshSet):
    w, d, h = FOOTPRINT["sofa"]
    f = ms["fabric_green"]
    f.box(-w / 2 + 0.15, -d / 2, 0.14, w / 2 - 0.15, d / 2 - 0.2, 0.46, tile=0.6)
    f.box(-w / 2, -d / 2 + 0.05, 0.14, -w / 2 + 0.16, d / 2, 0.64, tile=0.6)
    f.box(w / 2 - 0.16, -d / 2 + 0.05, 0.14, w / 2, d / 2, 0.64, tile=0.6)
    f.box(-w / 2, d / 2 - 0.22, 0.14, w / 2, d / 2, h, tile=0.6)
    for x in (-w / 2 + 0.1, w / 2 - 0.1):
        for y in (-d / 2 + 0.1, d / 2 - 0.1):
            ms["wood_dark"].cylinder(x, y, 0, 0.04, 0.03, 0.14, 8)


def bookshelf(ms: MeshSet):
    w, d, h = FOOTPRINT["bookshelf"]
    wd = ms["wood_dark"]
    wd.box(-w / 2, d / 2 - 0.03, 0, w / 2, d / 2, h, tile=1.0)                  # back
    wd.box(-w / 2, -d / 2, 0, -w / 2 + 0.04, d / 2, h, tile=1.0)
    wd.box(w / 2 - 0.04, -d / 2, 0, w / 2, d / 2, h, tile=1.0)
    shelves = 6
    for i in range(shelves + 1):
        z = 0.08 + i * (h - 0.12) / shelves
        wd.box(-w / 2 + 0.04, -d / 2, z, w / 2 - 0.04, d / 2 - 0.03, z + 0.03, tile=1.0)
        if i == shelves:
            break
        # books: deterministic pseudo-random widths, heights, colours
        x = -w / 2 + 0.06
        k = 0
        while x < w / 2 - 0.1:
            bw = 0.03 + ((i * 7 + k * 13) % 5) * 0.008
            bh = 0.18 + ((i * 3 + k * 11) % 4) * 0.025
            mat = ("fabric_red", "fabric_green", "wood_dark", "fabric_linen")[(i + k * 3) % 4]
            if (i * 5 + k) % 9 != 0:                        # a few gaps
                ms[mat].box(x, -d / 2 + 0.04 + (k % 3) * 0.01, z + 0.03, x + bw, d / 2 - 0.05, z + 0.03 + bh, tile=0.3)
            x += bw + 0.004
            k += 1
    wd.box(-w / 2 - 0.03, -d / 2 - 0.03, h - 0.06, w / 2 + 0.03, d / 2, h + 0.02, tile=1.0)   # cornice


def bed(ms: MeshSet):
    w, d, h = FOOTPRINT["bed"]
    wd = ms["wood_dark"]
    # headboard at +Y (against the wall)
    wd.box(-w / 2, d / 2 - 0.08, 0, w / 2, d / 2, 1.25, tile=1.0)
    for x in (-w / 2, w / 2 - 0.08):
        wd.cylinder(x + 0.04, d / 2 - 0.04, 0, 0.05, 0.05, 1.4, 10)
        ms["brass"].sphere(x + 0.04, d / 2 - 0.04, 1.44, 0.06, 10, 6)
    wd.box(-w / 2, -d / 2, 0, w / 2, -d / 2 + 0.08, 0.7, tile=1.0)                  # footboard
    wd.box(-w / 2 + 0.04, -d / 2 + 0.08, 0.15, w / 2 - 0.04, d / 2 - 0.08, 0.35, tile=1.0)
    ms["fabric_linen"].box(-w / 2 + 0.06, -d / 2 + 0.1, 0.35, w / 2 - 0.06, d / 2 - 0.1, 0.52, tile=0.6)
    ms["fabric_red"].box(-w / 2 + 0.02, -d / 2 + 0.08, 0.45, w / 2 - 0.02, d / 2 - 0.75, 0.56, tile=0.6)   # blanket
    for x in (-0.42, 0.42):
        ms["fabric_linen"].sphere(x, d / 2 - 0.42, 0.6, 0.3, 12, 8, scale=(1.2, 0.6, 0.3))


def nightstand(ms: MeshSet):
    w, d, h = FOOTPRINT["nightstand"]
    ms["wood_dark"].box(-w / 2, -d / 2, 0.05, w / 2, d / 2, h, tile=0.5)
    ms["brass"].sphere(0, -d / 2 - 0.01, h - 0.15, 0.02, 8, 5)
    _legs(ms["wood_dark"], w, d, 0.05, 0.04, 0.0)


def wardrobe(ms: MeshSet):
    w, d, h = FOOTPRINT["wardrobe"]
    wd = ms["wood_dark"]
    wd.box(-w / 2, -d / 2 + 0.03, 0.08, w / 2, d / 2, h, tile=1.0)
    wd.box(-w / 2 - 0.04, -d / 2, h - 0.08, w / 2 + 0.04, d / 2 + 0.02, h + 0.06, tile=1.0)
    for sx in (-1, 1):
        wd.box(sx * 0.02 if sx > 0 else -w / 2 + 0.04, -d / 2, 0.15,
               w / 2 - 0.04 if sx > 0 else -0.02, -d / 2 + 0.03, h - 0.12, tile=1.0)
        ms["brass"].box(sx * 0.06 - 0.01, -d / 2 - 0.02, 1.05, sx * 0.06 + 0.01, -d / 2, 1.25)
    _legs(wd, w, d, 0.08, 0.06, 0.02)


def dresser(ms: MeshSet):
    w, d, h = FOOTPRINT["dresser"]
    wd = ms["wood_dark"]
    wd.box(-w / 2, -d / 2 + 0.02, 0.08, w / 2, d / 2, h, tile=1.0)
    for i in range(3):
        z = 0.14 + i * 0.24
        wd.box(-w / 2 + 0.05, -d / 2, z, w / 2 - 0.05, -d / 2 + 0.02, z + 0.2, tile=1.0)
        for x in (-0.3, 0.3):
            ms["brass"].sphere(x, -d / 2 - 0.01, z + 0.1, 0.022, 8, 5)
    _legs(wd, w, d, 0.08, 0.05, 0.02)


def globe(ms: MeshSet):
    ms["wood_dark"].cylinder(0, 0, 0, 0.22, 0.05, 0.12, 12)
    ms["wood_dark"].cylinder(0, 0, 0.12, 0.03, 0.03, 0.55, 8)
    ms["brass"].box(-0.02, -0.02, 0.62, 0.02, 0.02, 1.08)
    ms["paper"].sphere(0, 0, 0.87, 0.21, 16, 10)


def bench(ms: MeshSet):
    w, d, h = FOOTPRINT["bench"]
    ms["fabric_red"].box(-w / 2, -d / 2, h - 0.1, w / 2, d / 2, h, tile=0.6)
    _legs(ms["wood_dark"], w, d, h - 0.1, 0.06, 0.05)


def clock(ms: MeshSet, three_am=False):
    w, d, h = FOOTPRINT["clock"]
    wd = ms["wood_dark"]
    wd.box(-w / 2 + 0.06, -d / 2 + 0.05, 0.25, w / 2 - 0.06, d / 2, 1.5, tile=1.0)     # trunk
    wd.box(-w / 2, -d / 2, 0, w / 2, d / 2, 0.25, tile=1.0)                              # base
    wd.box(-w / 2, -d / 2, 1.5, w / 2, d / 2, h - 0.1, tile=1.0)                          # hood
    wd.box(-w / 2 - 0.03, -d / 2 - 0.03, h - 0.1, w / 2 + 0.03, d / 2 + 0.02, h, tile=1.0)
    face_y = -d / 2 - 0.005
    fz = 1.82
    ms["ceramic"].box(-0.2, face_y - 0.005, fz - 0.2, 0.2, face_y + 0.001, fz + 0.2, uv_world=False)
    # hands: hour + minute (3:00 when wrong, 11:52 otherwise)
    hour_ang, min_ang = (90.0, 0.0) if three_am else (-15.0, -48.0)
    for ang, L, t in ((hour_ang, 0.11, 0.012), (min_ang, 0.16, 0.008)):
        a = math.radians(ang)
        # approximate a rotated hand with a chain of small boxes
        for s in range(6):
            f = (s + 0.5) / 6
            x, z = math.sin(a) * L * f, math.cos(a) * L * f
            ms["black"].box(x - t, face_y - 0.012, fz + z - t, x + t, face_y - 0.006, fz + z + t)
    # pendulum window + brass pendulum
    ms["black"].box(-0.12, -d / 2 + 0.04, 0.45, 0.12, -d / 2 + 0.05, 1.3)
    ms["brass"].box(-0.008, -d / 2 + 0.03, 0.75, 0.008, -d / 2 + 0.04, 1.25)
    ms["brass"].cylinder(0, -d / 2 + 0.035, 0.66, 0.07, 0.07, 0.02, 14)


def plinth(ms: MeshSet, fallen=False):
    w, d, h = FOOTPRINT["plinth"]
    ms["stone"].box(-w / 2, -d / 2, 0, w / 2, d / 2, 0.1, tile=1.0)
    ms["stone"].box(-w / 2 + 0.06, -d / 2 + 0.06, 0.1, w / 2 - 0.06, d / 2 - 0.06, h - 0.1, tile=1.0)
    ms["stone"].box(-w / 2, -d / 2, h - 0.1, w / 2, d / 2, h, tile=1.0)
    # a faceless bust
    ms["bone"].sphere(0, 0, h + 0.14, 0.16, 12, 6, scale=(1.3, 0.8, 0.9))
    ms["bone"].cylinder(0, 0, h + 0.2, 0.05, 0.05, 0.14, 10)
    ms["bone"].sphere(0, 0, h + 0.47, 0.12, 14, 10, scale=(0.85, 0.95, 1.2))


def coffee_table(ms: MeshSet):
    w, d, h = FOOTPRINT["coffee_table"]
    ms["wood_dark"].box(-w / 2, -d / 2, h - 0.04, w / 2, d / 2, h, tile=0.8)
    _legs(ms["wood_dark"], w, d, h - 0.04, 0.04, 0.05)


def piano(ms: MeshSet):
    w, d, h = FOOTPRINT["piano"]
    b = ms["black"]
    b.box(-w / 2, -d / 2 + 0.25, 0, w / 2, d / 2, h)
    b.box(-w / 2, -d / 2, 0.68, w / 2, -d / 2 + 0.25, 0.74)
    ms["ceramic"].box(-w / 2 + 0.08, -d / 2 + 0.02, 0.74, w / 2 - 0.08, -d / 2 + 0.2, 0.76)
    for i in range(36):
        if i % 7 in (0, 3):
            continue
        x = -w / 2 + 0.1 + i * (w - 0.2) / 36
        b.box(x, -d / 2 + 0.1, 0.76, x + 0.018, -d / 2 + 0.2, 0.785)
    for x in (-w / 2 + 0.05, w / 2 - 0.1):
        b.box(x, -d / 2, 0, x + 0.05, -d / 2 + 0.05, 0.68)


def floor_lamp(ms: MeshSet):
    ms["brass"].cylinder(0, 0, 0, 0.16, 0.12, 0.04, 14)
    ms["brass"].cylinder(0, 0, 0.04, 0.015, 0.015, 1.45, 8)
    ms["fabric_linen"].cylinder(0, 0, 1.38, 0.22, 0.13, 0.3, 16, caps=False)
    ms["glow_warm"].sphere(0, 0, 1.45, 0.06, 8, 6)


def desk_lamp(ms: MeshSet):
    ms["brass"].cylinder(0, 0, 0, 0.08, 0.06, 0.02, 12)
    ms["brass"].cylinder(0, 0, 0.02, 0.012, 0.012, 0.3, 6)
    ms["green_metal"].cylinder(0, 0, 0.28, 0.12, 0.05, 0.13, 14, caps=False)
    ms["glow_warm"].sphere(0, 0, 0.3, 0.035, 8, 5)


def candle(ms: MeshSet):
    ms["brass"].cylinder(0, 0, 0, 0.06, 0.05, 0.02, 10)
    ms["bone"].cylinder(0, 0, 0.02, 0.025, 0.025, 0.18, 8)
    ms["glow_warm"].sphere(0, 0, 0.225, 0.018, 6, 5, scale=(1, 1, 1.9))


def book_pile(ms: MeshSet):
    z = 0
    for i, (w, d, h, mat) in enumerate(((0.3, 0.22, 0.05, "fabric_red"), (0.26, 0.2, 0.04, "fabric_green"),
                                        (0.28, 0.21, 0.06, "wood_dark"))):
        o = (i - 1) * 0.02
        ms[mat].box(-w / 2 + o, -d / 2, z, w / 2 + o, d / 2, z + h, tile=0.3)
        z += h


def fireplace(ms: MeshSet):
    w, d, h = FOOTPRINT["fireplace"]
    st = ms["marble"]
    st.box(-w / 2, -d / 2, 0, -w / 2 + 0.3, d / 2, h - 0.12, tile=2)
    st.box(w / 2 - 0.3, -d / 2, 0, w / 2, d / 2, h - 0.12, tile=2)
    st.box(-w / 2 - 0.08, -d / 2 - 0.06, h - 0.12, w / 2 + 0.08, d / 2, h, tile=2)
    st.box(-w / 2 + 0.3, -d / 2, 0.85, w / 2 - 0.3, d / 2, h - 0.12, tile=2)
    ms["black"].box(-w / 2 + 0.3, -d / 2 + 0.1, 0, w / 2 - 0.3, d / 2, 0.85)
    ms["glow_ember"].box(-0.35, -0.05, 0.02, 0.35, 0.12, 0.08)


def mirror(ms: MeshSet):
    w, _, h = FOOTPRINT["mirror"]
    ms["brass"].box(-w / 2, -0.03, -h / 2, w / 2, 0.0, h / 2)
    ms["glass_dark"].box(-w / 2 + 0.06, -0.035, -h / 2 + 0.06, w / 2 - 0.06, -0.03, h / 2 - 0.06)


def rug(ms: MeshSet):
    w, d, _ = FOOTPRINT["rug"]
    ms["carpet"].box(-w / 2, -d / 2, 0.0, w / 2, d / 2, 0.012, tile=w, uv_world=False)


BUILDERS = {
    "desk": desk, "chair": chair, "armchair": armchair, "sofa": sofa, "bookshelf": bookshelf, "bed": bed,
    "nightstand": nightstand, "wardrobe": wardrobe, "dresser": dresser, "globe": globe, "bench": bench,
    "clock": clock, "plinth": plinth, "coffee_table": coffee_table, "piano": piano, "floor_lamp": floor_lamp,
    "desk_lamp": desk_lamp, "candle": candle, "book_pile": book_pile, "fireplace": fireplace,
    "mirror": mirror, "rug": rug,
}


def build(kind: str, ms: MeshSet, flags=frozenset()):
    fn = BUILDERS[kind]
    if kind == "clock":
        fn(ms, three_am="three_am" in flags)
    else:
        fn(ms)


def frame(ms: MeshSet, w: float, h: float, depth: float = 0.05, border: float = 0.07):
    """Picture frame facing -Y, centred on origin (x, z)."""
    g = ms["brass"]
    g.box(-w / 2 - border, -depth, h / 2, w / 2 + border, 0, h / 2 + border)
    g.box(-w / 2 - border, -depth, -h / 2 - border, w / 2 + border, 0, -h / 2)
    g.box(-w / 2 - border, -depth, -h / 2, -w / 2, 0, h / 2)
    g.box(w / 2, -depth, -h / 2, w / 2 + border, 0, h / 2)
    ms["canvas_back"].box(-w / 2, -0.012, -h / 2, w / 2, 0, h / 2, uv_world=False, faces="Y")
