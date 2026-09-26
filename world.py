"""Builds and updates the 3D mansion (Panda3D)."""
from __future__ import annotations

import math
import random

from panda3d.core import AmbientLight, DirectionalLight, PointLight, TransparencyAttrib

from . import props
from .geom import Mesh, MeshSet
from .layout import (AREAS, DOOR_H, HALL_H, ROOM_DOOR_HALF, ROOM_DOOR_X, ROOM_SLOTS, TREE_POSITIONS, WALLS,
                     WALL_T, WING_H)
from .rooms_data import FOOTPRINT, NIGHT_WRITING, RoomLayout, hall_items, to_world

TILE = {
    "damask": 2.0, "wall_study": 1.6, "wall_rose": 1.6, "wall_gallery": 1.6, "wall_parlour": 1.6,
    "stone": 3.0, "marble": 2.0, "wood": 3.0, "wood_dark": 1.2, "carpet": 2.5, "plaster": 3.0,
    "panel": 2.4, "grass": 4.0, "hedge": 2.5, "gravel": 3.0, "tile": 2.0, "roof": 3.0,
}
INTERIOR = {"damask", "panel", "room"}
KEY_MATERIAL = {"brass": "brass", "bone": "bone", "clock": "iron"}


class FlickerLight:
    """A point light whose brightness wobbles like a failing bulb or a flame."""

    def __init__(self, lnp, color, amount=0.1, speed=1.0, seed=0, flame=False):
        self.lnp, self.color, self.amount, self.speed, self.flame = lnp, color, amount, speed, flame
        self.rng = random.Random(seed)
        self.t = self.rng.uniform(0, 100)
        self.level = 1.0
        self.scale = 1.0          # external multiplier (hall stage, dread …)
        self.glows = []           # emissive nodes that follow this light

    def update(self, dt):
        self.t += dt * self.speed
        if self.flame:
            v = 1.0 - self.amount * (0.5 + 0.5 * math.sin(self.t * 9.1) * math.sin(self.t * 3.7 + 1.3))
        else:
            v = 1.0
            if self.rng.random() < self.amount * dt * 6:
                self.level = self.rng.choice((0.05, 0.2, 0.5))
            self.level += (1.0 - self.level) * min(1.0, dt * 9)
            v = self.level * (1 - self.amount * 0.15 * (0.5 + 0.5 * math.sin(self.t * 31)))
        v *= self.scale
        r, g, b = self.color
        self.lnp.node().setColor((r * v, g * v, b * v, 1))
        for gnode in self.glows:
            gnode.setColorScale(v, v, v, 1)


class World:
    def __init__(self, app, mats, settings):
        self.app = app
        self.mats = mats
        self.settings = settings
        self.root = app.render.attachNewNode("world")
        self.area_np = {a: self.root.attachNewNode(a) for a in ("hall", "corridor", "garden", "glasshouse")}
        self.slot_root = {s: self.root.attachNewNode(s) for s in ROOM_SLOTS}
        self.slot_dyn = {s: None for s in ROOM_SLOTS}
        self.slot_light: dict[str, FlickerLight] = {}
        self.slot_key_np = {s: None for s in ROOM_SLOTS}
        self.hall_dyn = None
        self.flickers: list[FlickerLight] = []
        self.room_wall_parts: dict[str, list] = {s: [] for s in ROOM_SLOTS}
        self.foliage = None
        self.orchid_np = None
        self.can_np = None
        self.front_leaves = []
        self.time = 0.0
        self._lights()
        self._static()

    # ==================================================================
    # Lights
    # ==================================================================
    def _lights(self):
        L = self.root.attachNewNode("lights")
        amb_in = AmbientLight("amb_in")
        amb_in.setColor((0.035, 0.035, 0.042, 1))
        self.amb_in = L.attachNewNode(amb_in)
        amb_out = AmbientLight("amb_out")
        amb_out.setColor((0.05, 0.06, 0.08, 1))
        self.amb_out = L.attachNewNode(amb_out)

        moon = DirectionalLight("moon")
        moon.setColor((0.32, 0.38, 0.5, 1))
        self.moon = L.attachNewNode(moon)
        self.moon.setPos(-28, 70, 40)
        self.moon.lookAt(0, 30, 0)
        if self.settings.get("shadows", True):
            moon.setShadowCaster(True, 2048, 2048)
            lens = moon.getLens()
            lens.setFilmSize(64, 64)
            lens.setNearFar(10, 110)

        def pl(name, pos, color, atten, amount, speed, seed, flame=False):
            p = PointLight(name)
            p.setColor((*color, 1))
            p.setAttenuation(atten)
            lnp = L.attachNewNode(p)
            lnp.setPos(*pos)
            fl = FlickerLight(lnp, color, amount, speed, seed, flame)
            self.flickers.append(fl)
            return fl

        self.chandelier = pl("chandelier", (0, 8, 5.0), (1.25, 0.9, 0.55), (1, 0.03, 0.012), 0.08, 1.0, 1, True)
        self.candelabra = pl("candelabra", (0, 8, 1.35), (1.0, 0.62, 0.32), (1, 0.15, 0.3), 0.3, 1.3, 2, True)
        self.corridor_lights = [
            pl(f"tube{i}", (x, 7.75, 3.3), (0.72, 0.82, 0.66), (1, 0.12, 0.1), 0.12 + 0.18 * i, 1.0, 10 + i)
            for i, x in enumerate((11.5, 19.5, 27.5))
        ]
        self.glass_light = pl("glasshouse", (0, 38, 3.4), (0.22, 0.4, 0.28), (1, 0.05, 0.02), 0.05, 0.4, 20, True)

        for a in ("hall",):
            self.area_np[a].setLight(self.amb_in)
            self.area_np[a].setLight(self.chandelier.lnp)
            self.area_np[a].setLight(self.candelabra.lnp)
        c = self.area_np["corridor"]
        c.setLight(self.amb_in)
        for fl in self.corridor_lights:
            c.setLight(fl.lnp)
        for s in ROOM_SLOTS:
            self.slot_root[s].setLight(self.amb_in)
        for a in ("garden", "glasshouse"):
            self.area_np[a].setLight(self.amb_out)
            self.area_np[a].setLight(self.moon)
            self.area_np[a].setLight(self.glass_light.lnp)

    # ==================================================================
    # Static geometry
    # ==================================================================
    def _static(self):
        sets = {a: MeshSet() for a in self.area_np}
        slot_sets = {s: MeshSet() for s in ROOM_SLOTS}
        e = WALL_T / 2

        # ---------------- walls (split into two faces) ----------------
        for w in WALLS:
            r = w.rect
            if w.axis == "x":
                cy = (r.y0 + r.y1) / 2
                halves = [(w.mat_a, (r.x0, r.y0, w.z0, r.x1, cy, w.z1), "xXyZz", "y"),
                          (w.mat_b, (r.x0, cy, w.z0, r.x1, r.y1, w.z1), "xXYZz", "Y")]
            else:
                cx = (r.x0 + r.x1) / 2
                halves = [(w.mat_a, (r.x0, r.y0, w.z0, cx, r.y1, w.z1), "xyYZz", "x"),
                          (w.mat_b, (cx, r.y0, w.z0, r.x1, r.y1, w.z1), "XyYZz", "X")]
            for mat, box, faces, face in halves:
                if mat == "room":
                    self._clip_room_half(box, faces, face, w)
                    continue
                target = w.area if w.area in sets else "corridor"
                if mat in ("stone", "hedge"):
                    target = "garden"
                ms = sets[target]
                ms[mat].box(*box, tile=TILE.get(mat, 2.0), faces=faces)
                if mat in INTERIOR and w.solid and mat != "room":
                    self._trim(ms, box, face, wainscot=(mat == "damask"))

        # ---------------- floors / ceilings ----------------
        H = sets["hall"]
        H["marble"].box(-8, 0, -0.2, 8, 16, 0, tile=TILE["marble"], faces="Z")
        H["plaster"].box(-8, 0, HALL_H, 8, 16, HALL_H + 0.2, tile=3.0, faces="z")
        # coffered ceiling beams
        for x in (-4, 0, 4):
            H["wood_dark"].box(x - 0.18, 0, HALL_H - 0.35, x + 0.18, 16, HALL_H, tile=1.5, faces="xXz")
        for y in (4, 8, 12):
            H["wood_dark"].box(-8, y - 0.18, HALL_H - 0.3, 8, y + 0.18, HALL_H, tile=1.5, faces="yYz")
        C = sets["corridor"]
        C["carpet"].box(8, 6.5, -0.2, 32, 9.0, 0, tile=TILE["carpet"], faces="Z")
        C["plaster"].box(8, 6.5, WING_H, 32, 9.0, WING_H + 0.2, tile=3.0, faces="z")
        for x in (11.5, 19.5, 27.5):
            C["iron"].box(x - 0.7, 7.6, WING_H - 0.06, x + 0.7, 7.9, WING_H)
            C["glow_white"].box(x - 0.65, 7.65, WING_H - 0.09, x + 0.65, 7.85, WING_H - 0.06)
        for s in ROOM_SLOTS:
            r = AREAS[s].rect
            ms = slot_sets[s]
            ms["wood"].box(r.x0, r.y0, -0.2, r.x1, r.y1, 0, tile=TILE["wood"], faces="Z")
            ms["plaster"].box(r.x0, r.y0, WING_H, r.x1, r.y1, WING_H + 0.2, tile=3.0, faces="z")
            ms["brass"].cylinder(r.cx, 12.5, WING_H - 0.25, 0.02, 0.02, 0.25, 6, caps=False)
            # door frame on both sides of the doorway
            dx = ROOM_DOOR_X[s]
            for side_y0, side_y1 in ((8.8, 8.85), (9.15, 9.2)):
                C["wood_dark"].box(dx - ROOM_DOOR_HALF - 0.12, side_y0, 0, dx - ROOM_DOOR_HALF, side_y1, DOOR_H + 0.1)
                C["wood_dark"].box(dx + ROOM_DOOR_HALF, side_y0, 0, dx + ROOM_DOOR_HALF + 0.12, side_y1, DOOR_H + 0.1)
                C["wood_dark"].box(dx - ROOM_DOOR_HALF - 0.12, side_y0, DOOR_H, dx + ROOM_DOOR_HALF + 0.12,
                                   side_y1, DOOR_H + 0.14)
        # roofs (seen from the garden against the moon)
        G = sets["garden"]
        G["roof"].prism_roof(-8.4, -0.4, 8.4, 16.4, HALL_H + 0.2, 3.4, tile=3.0)
        G["roof"].prism_roof(8.0, 6.2, 32.4, 16.4, WING_H + 0.2, 1.8, tile=3.0)
        G["grass"].box(-22, 16, -0.2, 22, 50, 0, tile=TILE["grass"], faces="Z")
        # gravel paths
        G["gravel"].box(-1.2, 16, 0, 1.2, 22.4, 0.015, tile=3.0, faces="Z")
        G["gravel"].box(-1.2, 25.6, 0, 1.2, 32, 0.015, tile=3.0, faces="Z")
        for x0, x1 in ((-2.8, -1.7), (1.7, 2.8)):
            G["gravel"].box(x0, 21.2, 0, x1, 26.8, 0.015, tile=3.0, faces="Z")
        G["gravel"].box(-2.8, 21.2, 0, 2.8, 22.3, 0.015, tile=3.0, faces="Z")
        G["gravel"].box(-2.8, 25.7, 0, 2.8, 26.8, 0.015, tile=3.0, faces="Z")
        GH = sets["glasshouse"]
        GH["tile"].box(-7, 32, 0, 7, 44, 0.02, tile=TILE["tile"], faces="Z")

        self._hall_static(H)
        self._corridor_static(C)
        self._garden_static(G)
        self._glasshouse_static(GH)

        for a, ms in sets.items():
            n = ms.build(self.area_np[a], self.mats, f"{a}_static")
            n.flattenStrong()
        for s, ms in slot_sets.items():
            n = ms.build(self.slot_root[s], self.mats, f"{s}_static")
            n.flattenStrong()
        self._sky()

    def _clip_room_half(self, box, faces, face, wall):
        """Split a wall face that shows room wallpaper between the slots it borders."""
        x0, y0, z0, x1, y1, z1 = box
        e = WALL_T / 2
        for s in ROOM_SLOTS:
            r = AREAS[s].rect
            cx0, cx1 = max(x0, r.x0 - e), min(x1, r.x1 + e)
            cy0, cy1 = max(y0, r.y0 - e), min(y1, r.y1 + e)
            if cx1 - cx0 > 0.01 and cy1 - cy0 > 0.01:
                self.room_wall_parts[s].append(((cx0, cy0, z0, cx1, cy1, z1), faces, face, wall.solid))

    @staticmethod
    def _trim(ms, box, face, wainscot=False, mat="wood_dark"):
        """Skirting board (and optional wainscot panelling) along an interior face."""
        x0, y0, z0, x1, y1, z1 = box
        if z0 > 0:
            return
        t = 0.03
        hs = 0.16
        if face == "y":
            ms[mat].box(x0, y0 - t, 0, x1, y0, hs, tile=1.2, faces="yZxX")
            if wainscot:
                ms["panel"].box(x0, y0 - 0.02, hs, x1, y0, 1.1, tile=TILE["panel"], faces="yxX")
                ms[mat].box(x0, y0 - 0.05, 1.1, x1, y0, 1.16, tile=1.2, faces="yZzxX")
        elif face == "Y":
            ms[mat].box(x0, y1, 0, x1, y1 + t, hs, tile=1.2, faces="YZxX")
            if wainscot:
                ms["panel"].box(x0, y1, hs, x1, y1 + 0.02, 1.1, tile=TILE["panel"], faces="YxX")
                ms[mat].box(x0, y1, 1.1, x1, y1 + 0.05, 1.16, tile=1.2, faces="YZzxX")
        elif face == "x":
            ms[mat].box(x0 - t, y0, 0, x0, y1, hs, tile=1.2, faces="xZyY")
            if wainscot:
                ms["panel"].box(x0 - 0.02, y0, hs, x0, y1, 1.1, tile=TILE["panel"], faces="xyY")
                ms[mat].box(x0 - 0.05, y0, 1.1, x0, y1, 1.16, tile=1.2, faces="xZzyY")
        elif face == "X":
            ms[mat].box(x1, y0, 0, x1 + t, y1, hs, tile=1.2, faces="XZyY")
            if wainscot:
                ms["panel"].box(x1, y0, hs, x1 + 0.02, y1, 1.1, tile=TILE["panel"], faces="XyY")
                ms[mat].box(x1, y0, 1.1, x1 + 0.05, y1, 1.16, tile=1.2, faces="XZzyY")

    # ------------------------------------------------------------------
    def _hall_static(self, H):
        # grand staircases up to a balcony along the north wall
        steps, top = 15, 3.0
        for sx, (xa, xb) in ((-1, (-7.8, -4.6)), (1, (4.6, 7.8))):
            for i in range(steps):
                y = 12.5 + i * (3.3 / steps)
                z = (i + 1) * top / steps
                H["marble"].box(xa, y, 0, xb, y + 3.3 / steps + 0.02, z, tile=2.0)
                H["fabric_red"].box(xa + 0.5, y, z, xb - 0.5, y + 3.3 / steps, z + 0.01, tile=1.0, faces="Z")
            inner = xb if sx < 0 else xa
            for i in range(0, steps, 2):
                y = 12.6 + i * (3.3 / steps)
                z = (i + 1) * top / steps
                H["wood_dark"].cylinder(inner, y, z, 0.035, 0.035, 0.9, 8, caps=False)
            H["wood_dark"].box(inner - 0.05, 12.5, 0, inner + 0.05, 12.6, 1.2)
        # balcony
        H["marble"].box(-7.85, 14.3, 2.85, 7.85, 15.85, 3.0, tile=2.0)
        H["wood_dark"].box(-7.85, 14.25, 2.6, 7.85, 14.35, 2.85, tile=1.2)
        for x in [i * 0.3 - 4.5 for i in range(31)]:
            H["wood_dark"].cylinder(x, 14.33, 3.0, 0.03, 0.03, 0.85, 6, caps=False)
        H["wood_dark"].box(-4.6, 14.28, 3.85, 4.6, 14.4, 3.93, tile=1.2)
        for x in (-3.0, 3.0):
            H["marble"].cylinder(x, 14.3, 0, 0.22, 0.2, 2.85, 16, tile=2.0)
        # long table with cloth, plates and a candelabra
        H["wood_dark"].box(-1.5, 7.2, 0.72, 1.5, 8.8, 0.78, tile=1.2)
        H["fabric_linen"].box(-1.55, 7.15, 0.78, 1.55, 8.85, 0.79, tile=1.0)
        H["fabric_linen"].box(-1.55, 7.15, 0.45, 1.55, 7.16, 0.79, tile=1.0)
        H["fabric_linen"].box(-1.55, 8.84, 0.45, 1.55, 8.85, 0.79, tile=1.0)
        for x in (-1.35, 1.35):
            for y in (7.35, 8.65):
                H["wood_dark"].box(x - 0.04, y - 0.04, 0, x + 0.04, y + 0.04, 0.72)
        for x, y in ((-1.0, 7.5), (-1.0, 8.5), (1.0, 7.5), (1.0, 8.5), (-0.5, 7.45), (0.5, 8.55)):
            H["ceramic"].cylinder(x, y, 0.79, 0.12, 0.13, 0.015, 18)
        H["brass"].cylinder(0, 8, 0.79, 0.12, 0.05, 0.05, 12)
        H["brass"].cylinder(0, 8, 0.84, 0.02, 0.02, 0.35, 8)
        H["brass"].cylinder(0, 8, 1.1, 0.22, 0.22, 0.02, 20)
        for a in range(5):
            ang = math.tau * a / 5
            x, y = math.cos(ang) * 0.18, 8 + math.sin(ang) * 0.18
            H["brass"].cylinder(x, y, 1.12, 0.035, 0.03, 0.02, 8)
            H["bone"].cylinder(x, y, 1.12, 0.022, 0.022, 0.16, 8)
            H["glow_warm"].sphere(x, y, 1.3, 0.018, 6, 5, scale=(1, 1, 2))
        # chandelier
        H["brass"].cylinder(0, 8, 5.4, 0.015, 0.015, HALL_H - 5.4, 6, caps=False)
        H["brass"].sphere(0, 8, 5.35, 0.22, 16, 10)
        H["brass"].cylinder(0, 8, 5.0, 0.7, 0.75, 0.05, 28, caps=True)
        for a in range(12):
            ang = math.tau * a / 12
            x, y = math.cos(ang) * 0.72, 8 + math.sin(ang) * 0.72
            H["bone"].cylinder(x, y, 5.05, 0.02, 0.02, 0.14, 6)
            H["glow_warm"].sphere(x, y, 5.24, 0.025, 6, 5, scale=(1, 1, 2))
        # rug under the table
        H["carpet"].box(-3.0, 4.5, 0, 3.0, 11.5, 0.01, tile=6.0, faces="Z", uv_world=False)
        # wall sconces
        for x, face in ((-7.83, 1), (7.83, -1)):
            for y in (3.0, 11.5):
                H["brass"].box(x, y - 0.05, 2.3, x + face * 0.2, y + 0.05, 2.34)
                H["glow_warm"].sphere(x + face * 0.2, y, 2.45, 0.05, 8, 6, scale=(1, 1, 1.6))
        # front double doors
        for sx in (-1, 1):
            leaf = self.area_np["hall"].attachNewNode(f"front_leaf{sx}")
            leaf.setPos(sx * 1.2, 0.0, 0)
            lm = MeshSet()
            x0, x1 = (0, 1.2) if sx < 0 else (-1.2, 0)
            lm["wood_dark"].box(x0, -0.08, 0, x1, 0.08, 3.6, tile=1.2)
            for zz in (0.4, 2.0):
                lm["wood_dark"].box(x0 + 0.15, 0.08, zz, x1 - 0.15, 0.11, zz + 1.3, tile=1.2)
            hx = x1 - 0.18 if sx < 0 else x0 + 0.18
            lm["brass"].sphere(hx, 0.14, 1.2, 0.05, 8, 6)
            lm.build(leaf, self.mats, "leaf")
            self.front_leaves.append((leaf, sx))
        # west wing door (locked, chained)
        H["wood_dark"].box(-8.12, 6.5, 0, -7.9, 9.0, 3.0, tile=1.2)
        for i in range(9):
            z = 1.1 + (i % 2) * 0.04
            H["iron"].box(-7.9, 6.9 + i * 0.2, z - 0.03, -7.86, 6.98 + i * 0.2, z + 0.03)
        H["iron"].box(-7.9, 7.6, 0.95, -7.82, 7.9, 1.2)
        # arch trim around the other doorways
        for (xa, xb, y) in ((-1.25, 1.25, 16.0),):
            H["wood_dark"].box(xa - 0.15, y - 0.22, 0, xa, y - 0.15, 3.6)
            H["wood_dark"].box(xb, y - 0.22, 0, xb + 0.15, y - 0.15, 3.6)
            H["wood_dark"].box(xa - 0.15, y - 0.22, 3.6, xb + 0.15, y - 0.15, 3.78)
        H["wood_dark"].box(7.78, 6.35, 0, 7.85, 6.5, 3.0)
        H["wood_dark"].box(7.78, 9.0, 0, 7.85, 9.15, 3.0)
        H["wood_dark"].box(7.78, 6.35, 3.0, 7.85, 9.15, 3.15)

    def _corridor_static(self, C):
        # a narrow console with a vase of dead flowers
        C["wood_dark"].box(15.0, 6.66, 0.8, 16.4, 7.05, 0.84)
        for x in (15.1, 16.3):
            C["wood_dark"].box(x - 0.03, 6.7, 0, x + 0.03, 6.76, 0.8)
        C["ceramic"].cylinder(15.7, 6.86, 0.84, 0.08, 0.1, 0.28, 12)
        for i in range(5):
            C["bark"].cylinder(15.7 + (i - 2) * 0.02, 6.86, 1.1, 0.006, 0.004, 0.32 - i * 0.02, 5, caps=False)

    def _garden_static(self, G):
        # fountain
        G["stone"].cylinder(0, 24, 0, 1.6, 1.65, 0.55, 32, tile=2.0)
        G["water"].cylinder(0, 24, 0.44, 1.45, 1.45, 0.02, 32)
        G["stone"].cylinder(0, 24, 0.55, 0.22, 0.18, 1.1, 14, tile=2.0)
        G["stone"].cylinder(0, 24, 1.6, 0.25, 0.65, 0.25, 20, tile=2.0)
        G["stone"].sphere(0, 24, 2.0, 0.18, 12, 8, scale=(1, 1, 1.6))
        # benches
        for x in (-5.0, 5.0):
            for i in range(4):
                G["wood_dark"].box(x - 1.0, 26.5 + i * 0.16, 0.44, x + 1.0, 26.62 + i * 0.16, 0.48, tile=1.2)
            G["wood_dark"].box(x - 1.0, 27.18, 0.5, x + 1.0, 27.22, 0.95, tile=1.2)
            for dx in (-0.85, 0.85):
                G["iron"].box(x + dx - 0.03, 26.5, 0, x + dx + 0.03, 27.2, 0.44)
        # garden shed
        G["wood_dark"].box(-20.5, 44.0, 0, -16.5, 48.5, 2.4, tile=1.2)
        G["roof"].prism_roof(-20.8, 43.7, -16.2, 48.8, 2.4, 1.0, tile=2.0)
        G["black"].box(-19.4, 43.97, 0, -18.4, 44.0, 2.0)
        # lanterns along the path
        for x in (-2.2, 2.2):
            for y in (18.5,):
                G["iron"].cylinder(x, y, 0, 0.08, 0.05, 2.4, 8)
                G["iron"].box(x - 0.14, y - 0.14, 2.4, x + 0.14, y + 0.14, 2.44)
                G["glow_warm"].box(x - 0.1, y - 0.1, 2.44, x + 0.1, y + 0.1, 2.72)
                G["iron"].cylinder(x, y, 2.72, 0.18, 0.0, 0.18, 4)

        # foliage lives in its own node so the garden can wither
        F = MeshSet()
        for i, (x, y) in enumerate(TREE_POSITIONS):
            F["bark"].cylinder(x, y, 0, 0.42, 0.22, 4.2, 12, tile=2.0)
            rng = random.Random(i)
            for k in range(6):
                F["leaves"].sphere(x + rng.uniform(-1.4, 1.4), y + rng.uniform(-1.4, 1.4),
                                   4.4 + rng.uniform(-0.6, 1.4), rng.uniform(1.2, 1.9), 14, 9,
                                   scale=(1, 1, 0.75), tile=2.5)
        for x in (-2.0, 2.0):
            for y in (17.8, 30.5):
                F["leaves"].cylinder(x, y, 0.3, 0.45, 0.0, 1.8, 16, tile=1.5)
                F["terracotta"].cylinder(x, y, 0, 0.35, 0.42, 0.35, 16, tile=1.0)
        # flower beds along the hedges
        rng = random.Random(9)
        for k in range(40):
            side = k % 4
            if side == 0:
                x, y = -21.2, rng.uniform(18, 48)
            elif side == 1:
                x, y = 21.2, rng.uniform(18, 48)
            elif side == 2:
                x, y = rng.uniform(-20, 20), 49.2
            else:
                x, y = rng.uniform(-20, -10), 16.8
            F["leaves"].sphere(x, y, 0.2, rng.uniform(0.35, 0.6), 10, 6, scale=(1, 1, 0.7), tile=1.0)
        self.foliage = F.build(self.area_np["garden"], self.mats, "foliage")
        self.foliage.flattenStrong()

    def _glasshouse_static(self, GH):
        # iron frame
        for x in [-7 + i * 2 for i in range(8)]:
            for y in (32, 44):
                GH["iron"].box(x - 0.04, y - 0.06, 0, x + 0.04, y + 0.06, 4.2)
        for y in [32 + i * 2 for i in range(7)]:
            for x in (-7, 7):
                GH["iron"].box(x - 0.06, y - 0.04, 0, x + 0.06, y + 0.04, 4.2)
        for y in (32, 44):
            GH["iron"].box(-7.08, y - 0.08, 4.12, 7.08, y + 0.08, 4.25)
            GH["iron"].box(-7.08, y - 0.08, 0.8, 7.08, y + 0.08, 0.86)
        for x in (-7, 7):
            GH["iron"].box(x - 0.08, 32, 4.12, x + 0.08, 44, 4.25)
            GH["iron"].box(x - 0.08, 32, 0.8, x + 0.08, 44, 0.86)
        GH["iron"].box(-7.0, 37.95, 5.95, 7.0, 38.05, 6.05)
        GH["glass"].prism_roof(-7.0, 32.0, 7.0, 44.0, 4.2, 1.8, tile=4.0)
        # planters along the walls with plants
        rng = random.Random(4)
        for x0, x1, y0, y1 in ((-6.8, -5.6, 33, 43), (5.6, 6.8, 33, 43)):
            GH["wood_dark"].box(x0, y0, 0, x1, y1, 0.6, tile=1.2)
            GH["soil"].box(x0 + 0.05, y0 + 0.05, 0.6, x1 - 0.05, y1 - 0.05, 0.62, faces="Z", tile=1.0)
            for k in range(9):
                cx = (x0 + x1) / 2
                cy = y0 + 0.6 + k * 1.1
                GH["leaves"].sphere(cx + rng.uniform(-0.2, 0.2), cy, 0.9 + rng.uniform(0, 0.3),
                                    rng.uniform(0.35, 0.55), 10, 7, scale=(1, 1, 1.3), tile=1.0)
        # orchid plinth
        GH["marble"].box(-0.5, 39.5, 0, 0.5, 40.5, 0.9, tile=2.0)
        GH["marble"].box(-0.58, 39.42, 0.9, 0.58, 40.58, 0.98, tile=2.0)

    def _sky(self):
        m = Mesh()
        m.sphere(0, 0, 0, 180, 32, 16, inside=True)
        sky = m.node("sky")
        sky.reparentTo(self.app.camera)
        sky.setCompass()                     # keep upright while the camera turns
        sky.setTexture(self.mats.tex("sky"), 1)
        sky.setLightOff(1)
        sky.setFogOff(1)
        sky.setShaderOff(1)
        sky.setBin("background", 0)
        sky.setDepthWrite(False)
        sky.setDepthTest(False)
        self.sky = sky
        mq = Mesh()
        mq.box(-9, 0, -9, 9, 0.01, 9, uv_world=False, faces="y")
        moon = mq.node("moon")
        moon.reparentTo(sky)
        moon.setPos(-85, 110, 95)
        moon.lookAt(0, 0, 0)
        moon.setTexture(self.mats.clamp_tex("moon"), 1)
        moon.setTransparency(TransparencyAttrib.MAlpha)
        moon.setLightOff(1)
        moon.setColorScale(1.35, 1.35, 1.3, 1)
        moon.setBin("background", 1)
        moon.setDepthWrite(False)
        moon.setDepthTest(False)
        moon.setTwoSided(True)

    # ==================================================================
    # Dynamic content
    # ==================================================================
    def _textured_quad(self, parent, w, h, texname, face="y", clamp=True, alpha=False):
        m = Mesh()
        if face == "y":
            m.box(-w / 2, -0.001, -h / 2, w / 2, 0, h / 2, uv_world=False, faces="y")
        else:  # floor decal
            m.box(-w / 2, -h / 2, 0, w / 2, h / 2, 0.001, uv_world=False, faces="Z")
        n = m.node(texname)
        n.reparentTo(parent)
        n.setTexture(self.mats.clamp_tex(texname) if clamp else self.mats.tex(texname), 1)
        n.setMaterial(self.mats.material("fabric_linen"), 1)
        n.setColorScale(1, 1, 1, 1)
        if alpha:
            n.setTransparency(TransparencyAttrib.MAlpha)
            n.setDepthWrite(False)
            n.setDepthOffset(2)
        return n

    def _build_item(self, parent, kind, x, y, rot, z=0.0, flags=frozenset()):
        ms = MeshSet()
        props.build(kind, ms, flags)
        holder = parent.attachNewNode(kind)
        holder.setPos(x, y, z)
        holder.setH(rot)
        pivot = holder.attachNewNode("pivot")
        body = ms.build(pivot, self.mats, kind)
        w, d, h = FOOTPRINT[kind]
        if "fallen" in flags:
            body.setZ(-h / 2)
            pivot.setR(90)
            holder.setZ(z + min(w, 0.9) / 2)
        elif "upside" in flags:
            body.setZ(-h / 2)
            pivot.setR(180)
            holder.setZ(z + h / 2)
        return holder

    def _build_wall_item(self, parent, kind, x, y, z, h_deg, flags, art=0, text=None, size=None):
        holder = parent.attachNewNode(kind)
        holder.setPos(x, y, z)
        holder.setH(h_deg)
        if "inverted" in flags:
            holder.setR(180)
        elif "askew" in flags:
            holder.setR(9)
        if kind in ("painting", "portrait"):
            pw, ph = size or (0.8, 1.0)
            ms = MeshSet()
            props.frame(ms, pw, ph)
            if "turned" in flags:
                # only the back of the canvas faces the room now
                ms["canvas_back"].box(-pw / 2 - 0.07, -0.06, -ph / 2 - 0.07, pw / 2 + 0.07, -0.05,
                                      ph / 2 + 0.07, uv_world=False)
            ms.build(holder, self.mats, kind)
            if "turned" not in flags:
                q = self._textured_quad(holder, pw, ph, f"painting_{art % 8}")
                q.setY(-0.015)
        elif kind == "mirror":
            ms = MeshSet()
            props.mirror(ms)
            ms.build(holder, self.mats, kind)
        elif kind == "writing":
            idx = NIGHT_WRITING.index(text) if text in NIGHT_WRITING else 0
            q = self._textured_quad(holder, 2.4, 0.6, f"writing_{idx}", alpha=True)
            q.setY(-0.004)
        return holder

    # ------------------------------------------------------------------
    def build_room(self, slot: str, layout: RoomLayout, keys_taken: set[str], seed: int = 0):
        if self.slot_dyn[slot] is not None:
            self.slot_dyn[slot].removeNode()
        if slot in self.slot_light:
            fl = self.slot_light.pop(slot)
            self.slot_root[slot].clearLight(fl.lnp)
            self.flickers.remove(fl)
            fl.lnp.removeNode()
        dyn = self.slot_root[slot].attachNewNode("dyn")
        self.slot_dyn[slot] = dyn
        static = dyn.attachNewNode("static")
        r = AREAS[slot].rect

        # walls in this identity's wallpaper, plus skirting
        ms = MeshSet()
        for box, faces, face, solid in self.room_wall_parts[slot]:
            ms[layout.wall_mat].box(*box, tile=1.6, faces=faces)
            if solid:
                self._trim(ms, box, face)
        # the ceiling rose + lamp glow in the lamp colour
        glow_mat = "glow_red" if layout.variant == "night" else "glow_warm"
        ms["brass"].cylinder(r.cx, 12.5, WING_H - 0.32, 0.18, 0.06, 0.1, 14)
        ms[glow_mat].sphere(r.cx, 12.5, WING_H - 0.4, 0.09, 10, 7)
        ms.build(static, self.mats, "shell")

        for it in layout.items:
            x, y = to_world(slot, it.lx, it.ly)
            if it.wall:
                if it.wall == "n":
                    pos, hd = (r.x0 + it.lx, r.y1 - WALL_T / 2, it.z), 0
                elif it.wall == "w":
                    pos, hd = (r.x0 + WALL_T / 2, r.y0 + it.ly, it.z), 90
                else:
                    pos, hd = (r.x1 - WALL_T / 2, r.y0 + it.ly, it.z), 270
                size = (0.9, 1.1) if it.kind == "painting" else None
                self._build_wall_item(static, it.kind, *pos, hd, it.flags, it.art, it.text, size)
            elif it.kind == "stain":
                q = self._textured_quad(static, 1.3, 1.3, f"stain_{seed % 3}", face="z", alpha=True)
                q.setPos(x, y, 0.004)
                q.setH((seed * 47 + int(it.lx * 100)) % 360)
            else:
                self._build_item(static, it.kind, x, y, it.rot, it.z, it.flags)
        static.flattenStrong()

        # lamp
        p = PointLight(f"{slot}_lamp")
        lnp = self.root.attachNewNode(p)
        lnp.setPos(r.cx, 12.3, WING_H - 0.7)
        p.setAttenuation((1, 0.12, 0.16))
        col = tuple(c * layout.lamp_power for c in layout.lamp_color)
        fl = FlickerLight(lnp, col, layout.flicker, 1.0 + seed % 3 * 0.3, seed)
        self.flickers.append(fl)
        self.slot_light[slot] = fl
        self.slot_root[slot].setLight(lnp)

        # key
        self.slot_key_np[slot] = None
        if layout.key and layout.key.key_id not in keys_taken:
            kx, ky = to_world(slot, layout.key.lx, layout.key.ly)
            self.slot_key_np[slot] = self._build_key(dyn, layout.key.key_id, kx, ky, layout.key.z)

    def _build_key(self, parent, key_id, x, y, z):
        ms = MeshSet()
        mat = KEY_MATERIAL[key_id]
        for a in range(12):                      # bow (a ring of small boxes)
            ang = math.tau * a / 12
            cx, cz = math.cos(ang) * 0.028, math.sin(ang) * 0.028
            ms[mat].box(cx - 0.008, -0.004, cz - 0.008 + 0.06, cx + 0.008, 0.004, cz + 0.008 + 0.06)
        ms[mat].box(-0.006, -0.004, -0.07, 0.006, 0.004, 0.035)
        ms[mat].box(0.006, -0.004, -0.07, 0.03, 0.004, -0.055)
        ms[mat].box(0.006, -0.004, -0.045, 0.024, 0.004, -0.035)
        ms["glow_warm" if key_id != "bone" else "glow_white"].sphere(0, 0, 0.06, 0.006, 6, 4)
        holder = parent.attachNewNode(f"key_{key_id}")
        holder.setPos(x, y, z + 0.09)
        ms.build(holder, self.mats, "key")
        holder.setP(-80)                         # lying almost flat
        holder.setScale(1.4)
        return holder

    def take_key(self, slot):
        np_ = self.slot_key_np.get(slot)
        if np_ is not None:
            np_.removeNode()
        self.slot_key_np[slot] = None

    # ------------------------------------------------------------------
    def build_hall_stage(self, stage: int):
        if self.hall_dyn is not None:
            self.hall_dyn.removeNode()
        dyn = self.area_np["hall"].attachNewNode("hall_dyn")
        self.hall_dyn = dyn
        for it in hall_items(stage):
            flags = frozenset(it["flags"])
            if it["kind"] == "portrait":
                if abs(it["y"] - 0.15) < 0.01:
                    hd, pos = 180, (it["x"], 0.15, 2.4)
                else:
                    hd, pos = 90, (-7.85, it["y"], 2.4)
                art = int(abs(it["x"]) + it["y"]) % 8
                self._build_wall_item(dyn, "portrait", *pos, hd, flags, art=(0, 3, 6, 3)[art % 4],
                                      size=(1.1, 1.4))
            else:
                self._build_item(dyn, it["kind"], it["x"], it["y"], it["rot"], 0.0, flags)
        dyn.flattenStrong()
        self.chandelier.scale = (1.0, 0.8, 0.6, 0.38)[stage]
        self.candelabra.scale = (1.0, 0.9, 0.75, 0.6)[stage]

    # ------------------------------------------------------------------
    def build_orchid(self, watered: bool, stage: int):
        if self.orchid_np is not None:
            self.orchid_np.removeNode()
        ms = MeshSet()
        ms["terracotta"].cylinder(0, 40, 0.98, 0.14, 0.18, 0.22, 16, tile=1.0)
        ms["soil"].cylinder(0, 40, 1.19, 0.16, 0.16, 0.01, 16, tile=1.0)
        alive = watered or stage < 2
        leaf = "leaves"
        for k in range(4):
            a = k * 1.7
            ms[leaf].sphere(math.cos(a) * 0.14, 40 + math.sin(a) * 0.14, 1.24, 0.14, 10, 6,
                            scale=(1.2, 0.5, 0.18))
        ms["bark"].cylinder(0, 40, 1.2, 0.008, 0.006, 0.45, 5, caps=False)
        petal = "petal" if alive else "bark"
        for k in range(5):
            ms[petal].sphere(0.06 * math.cos(k * 1.3), 40 + 0.03 * k - 0.06, 1.55 + 0.06 * math.sin(k * 2),
                             0.05, 8, 6, scale=(1.3, 0.5, 1.0))
        if watered:
            ms["glow_green"].sphere(0, 40, 1.58, 0.012, 6, 4)
        self.orchid_np = ms.build(self.area_np["glasshouse"], self.mats, "orchid")
        if not alive:
            self.orchid_np.setColorScale(0.55, 0.45, 0.35, 1)

    def build_can(self, visible: bool):
        if self.can_np is not None:
            self.can_np.removeNode()
            self.can_np = None
        if not visible:
            return
        ms = MeshSet()
        ms["green_metal"].cylinder(0, 0, 0, 0.13, 0.12, 0.3, 16)
        ms["green_metal"].box(0.1, -0.02, 0.05, 0.36, 0.02, 0.09)
        ms["green_metal"].cylinder(0.38, 0, 0.07, 0.04, 0.06, 0.08, 8)
        ms["green_metal"].box(-0.02, -0.015, 0.3, 0.02, 0.015, 0.42)
        ms["green_metal"].box(-0.12, -0.015, 0.4, 0.12, 0.015, 0.43)
        self.can_np = ms.build(self.area_np["garden"], self.mats, "can")
        self.can_np.setPos(2.4, 31.1, 0.0)
        self.can_np.setH(200)

    def set_garden_stage(self, stage: int):
        """0 = lush and moonlit … 3 = withered, grey, fog-choked."""
        tint = [(1, 1, 1), (0.85, 0.8, 0.7), (0.62, 0.55, 0.42), (0.45, 0.4, 0.33)][stage]
        self.foliage.setColorScale(*tint, 1)
        moon = [(0.34, 0.4, 0.52), (0.3, 0.34, 0.44), (0.25, 0.26, 0.33), (0.22, 0.17, 0.2)][stage]
        self.moon.node().setColor((*moon, 1))
        self.glass_light.scale = (1.0, 0.8, 0.5, 0.25)[stage]

    def open_front_door(self, t: float):
        """t 0..1 swings the leaves inward."""
        for leaf, sx in self.front_leaves:
            leaf.setH(-sx * 100 * t)

    # ------------------------------------------------------------------
    def update(self, dt: float):
        self.time += dt
        for fl in self.flickers:
            fl.update(dt)
        for s, np_ in self.slot_key_np.items():
            if np_ is not None:
                np_.setH(self.time * 25)
