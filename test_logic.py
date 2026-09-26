"""Logic tests — run with:  python -m unittest discover -s tests"""
import math
import os
import sys
import unittest
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import nav  # noqa: E402
from game.layout import (AREAS, DOORS, PLAYER_R, PLAYER_START, ROOM_DOOR_X, ROOM_SLOTS, STATIC_OBSTACLES,  # noqa: E402
                         WALLS, Rect, area_at, sight_rects, solid_rects)
from game.objectives import Progress  # noqa: E402
from game.physics import (angle_to, forward_2d, line_clear, move_and_collide, point_free,  # noqa: E402
                          segment_hits_rect)
from game.rooms_data import (IDENTITIES, KEY_HOMES, VARIANTS, colliders, hall_colliders,  # noqa: E402
                             room_layout, to_world)
from game.shifting import ShiftManager  # noqa: E402
from game.walker_ai import WalkerBrain  # noqa: E402


def reachable(start, goal, rects, r=PLAYER_R, reach=1.0, step=0.2):
    """Grid BFS: can a body of radius r walk from start to within `reach` of goal?"""
    sx, sy = start
    q = deque([(round(sx / step), round(sy / step))])
    seen = set(q)
    while q:
        i, j = q.popleft()
        x, y = i * step, j * step
        if math.hypot(x - goal[0], y - goal[1]) <= reach:
            return True
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (i + di, j + dj)
            if n in seen:
                continue
            nx, ny = n[0] * step, n[1] * step
            if not (-23 < nx < 33 and -1 < ny < 51):
                continue
            if point_free(nx, ny, r, rects):
                seen.add(n)
                q.append(n)
    return False


class PhysicsTests(unittest.TestCase):
    def test_slide_along_wall(self):
        wall = Rect(0, 1, 10, 1.3)
        x, y = move_and_collide(5, 0, 1.0, 2.0, 0.3, [wall])
        self.assertAlmostEqual(x, 6.0, places=3)
        self.assertLess(y, 0.7 + 1e-3)

    def test_no_tunnelling(self):
        wall = Rect(0, 1, 10, 1.3)
        _, y = move_and_collide(5, 0, 0, 20, 0.3, [wall])
        self.assertLess(y, 1.0)

    def test_segment(self):
        rc = Rect(0, 0, 1, 1)
        self.assertTrue(segment_hits_rect(-1, 0.5, 2, 0.5, rc))
        self.assertFalse(segment_hits_rect(-1, 2, 2, 2, rc))
        self.assertFalse(segment_hits_rect(-1, 0.5, -0.5, 0.5, rc))

    def test_heading(self):
        fx, fy = forward_2d(0)
        self.assertAlmostEqual(fx, 0, places=6)
        self.assertAlmostEqual(fy, 1, places=6)
        fx, fy = forward_2d(90)          # Panda: +90 heading turns left → west
        self.assertAlmostEqual(fx, -1, places=6)
        self.assertAlmostEqual(angle_to(0, 0, 0, 0, 5), 0, places=4)
        self.assertAlmostEqual(angle_to(0, 0, 0, 0, -5), 180, places=4)


class LayoutTests(unittest.TestCase):
    def test_start_is_free(self):
        x, y, _ = PLAYER_START
        self.assertTrue(point_free(x, y, PLAYER_R, solid_rects(hall_colliders(0))))
        self.assertEqual(area_at(x, y), "hall")

    def test_everything_reachable(self):
        rects = solid_rects(hall_colliders(3))
        for slot in ROOM_SLOTS:
            rects += colliders(slot, room_layout(*{"room_a": ("study", "quiet"),
                                                     "room_b": ("bedroom", "quiet"),
                                                     "room_c": ("gallery", "quiet")}[slot]))
        start = PLAYER_START[:2]
        targets = {
            "hall note": (0, 8.0),
            "corridor end": (31, 7.75),
            "glasshouse orchid": (0, 40.0),
            "garden far corner": (-18, 30),
            "front door": (0, 0.2),
        }
        for name, t in targets.items():
            with self.subTest(name):
                self.assertTrue(reachable(start, t, rects, reach=1.6), name)

    def test_walls_have_no_duplicates(self):
        seen = set()
        for w in WALLS:
            key = (round(w.rect.x0, 3), round(w.rect.y0, 3), round(w.rect.x1, 3), round(w.rect.y1, 3), w.z0)
            self.assertNotIn(key, seen)
            seen.add(key)


class RoomTests(unittest.TestCase):
    def test_every_layout_is_valid(self):
        for ident in IDENTITIES:
            for var in VARIANTS:
                for seed in range(4):
                    lay = room_layout(ident, var, seed)
                    for slot in ROOM_SLOTS:
                        room = AREAS[slot].rect
                        door = Rect(ROOM_DOOR_X[slot] - 1.0, 9.0, ROOM_DOOR_X[slot] + 1.0, 10.6)
                        for rc in colliders(slot, lay):
                            with self.subTest(ident=ident, var=var, slot=slot, rc=rc):
                                self.assertGreaterEqual(rc.x0, room.x0 + 0.15)
                                self.assertLessEqual(rc.x1, room.x1 - 0.15)
                                self.assertGreaterEqual(rc.y0, room.y0 + 0.15)
                                self.assertLessEqual(rc.y1, room.y1 - 0.15)
                                self.assertFalse(rc.intersects(door), "blocks the doorway")

    def test_keys_reachable_in_every_slot(self):
        for key_id, (ident, var) in KEY_HOMES.items():
            lay = room_layout(ident, var)
            self.assertIsNotNone(lay.key)
            for slot in ROOM_SLOTS:
                with self.subTest(key=key_id, slot=slot):
                    rects = solid_rects(colliders(slot, lay))
                    goal = to_world(slot, lay.key.lx, lay.key.ly)
                    # interaction reach is 2.5 m from the eye; allow 1.9 m on the floor plane
                    self.assertTrue(reachable((ROOM_DOOR_X[slot], 7.75), goal, rects, reach=1.9))


class NavTests(unittest.TestCase):
    def test_nodes_are_free_and_edges_clear(self):
        rects = solid_rects(hall_colliders(0), include_locked_doors=True)
        for n, (x, y) in nav.NODES.items():
            with self.subTest(node=n):
                self.assertTrue(point_free(x, y, 0.28, rects), n)
        grown = [r.expanded(0.2) for r in rects]
        for a, b in nav.EDGES:
            with self.subTest(edge=(a, b)):
                self.assertTrue(line_clear(*nav.NODES[a], *nav.NODES[b], grown), (a, b))

    def test_graph_connected(self):
        for n in nav.NODES:
            self.assertTrue(nav.shortest_path("H_S", n, True), n)

    def test_garden_blocked_early(self):
        self.assertEqual(nav.shortest_path("H_S", "GH_N", False), [])


class ShiftTests(unittest.TestCase):
    def test_no_shift_while_watching(self):
        sm = ShiftManager(seed=3)
        sm.update("room_a", {}, {}, set())
        before = sm.config("room_a")
        shifted = sm.update("corridor", {"room_a": True}, {"room_a": 2.0}, set())
        self.assertEqual(shifted, [])
        self.assertEqual(sm.config("room_a"), before)
        shifted = sm.update("corridor", {"room_a": False}, {"room_a": 2.0}, set())
        self.assertEqual(shifted, ["room_a"])
        self.assertNotEqual(sm.config("room_a"), before)

    def test_identities_unique_and_keys_appear(self):
        for seed in range(30):
            sm = ShiftManager(seed=seed)
            found: set[str] = set()
            for i in range(40):
                for slot in ("room_a", "room_b", "room_c"):
                    cfg = sm.config(slot)
                    for kid, home in KEY_HOMES.items():
                        if home == cfg:
                            found.add(kid)
                idents = [s.identity for s in sm.slots.values()]
                self.assertEqual(len(idents), len(set(idents)))
                slot = ("room_a", "room_b", "room_c")[i % 3]
                sm.update(slot, {}, {}, found)
                sm.update("corridor", {}, {}, found)
                if len(found) == 3:
                    break
            self.assertEqual(len(found), 3, f"seed {seed}")


class WalkerTests(unittest.TestCase):
    def setUp(self):
        self.solid = solid_rects(hall_colliders(1))
        self.sight = sight_rects()

    def test_freezes_when_seen(self):
        w = WalkerBrain(active=True, x=0, y=12)
        w.update(0.5, 0, 3, 0, True, 1, self.solid, self.sight)   # player looks north at it
        self.assertEqual((w.x, w.y), (0, 12))
        self.assertTrue(w.seen)

    def test_moves_when_unseen(self):
        w = WalkerBrain(active=True, x=0, y=12)
        w.update(0.5, 0, 3, 180, True, 1, self.solid, self.sight)  # player looks south, away
        self.assertLess(w.y, 12)

    def test_hunts_through_corridor(self):
        w = WalkerBrain(active=True, x=-5, y=3)
        px, py, heading = 21.0, 12.0, 0.0   # player inside room B looking at back wall
        events = []
        for _ in range(900):
            events += w.update(1 / 30, px, py, heading, True, 1, self.solid, self.sight)
            if "caught" in events:
                break
        self.assertIn("caught", events)

    def test_garden_safe_early(self):
        w = WalkerBrain(active=True, x=0, y=10)
        for _ in range(600):
            ev = w.update(1 / 30, 0, 38, 0, True, 1, self.solid, self.sight)
            self.assertNotIn("caught", ev)
        self.assertNotIn(area_at(w.x, w.y), ("garden", "glasshouse"))


class ProgressTests(unittest.TestCase):
    def test_chain(self):
        p = Progress()
        self.assertIn("note", p.objective())
        p.read_note = True
        for k in KEY_HOMES:
            p.take_key(k)
        self.assertFalse(p.front_door_open)
        p.has_can = True
        p.orchid_watered = True
        self.assertTrue(p.front_door_open)
        self.assertEqual(p.garden_stage, 3)


if __name__ == "__main__":
    unittest.main()


class GeomTests(unittest.TestCase):
    def _check(self, m, flip=False):
        from game.geom import _cross, _dot, _sub
        bad = 0
        for k in range(0, len(m.idx), 3):
            a, b, c = (m.pos[i] for i in m.idx[k:k + 3])
            n = m.nrm[m.idx[k]]
            fn = _cross(_sub(b, a), _sub(c, a))
            if _dot(fn, fn) < 1e-12:
                continue            # degenerate (sphere poles)
            if _dot(fn, n) <= 0:
                bad += 1
        self.assertEqual(bad, 0)

    def test_windings(self):
        from game.geom import Mesh
        m = Mesh(); m.box(0, 0, 0, 1, 2, 3); self._check(m)
        m = Mesh(); m.cylinder(0, 0, 0, 1, 0.5, 2); self._check(m)
        m = Mesh(); m.cylinder(0, 0, 0, 1, 0.0, 2); self._check(m)
        m = Mesh(); m.sphere(0, 0, 0, 1, scale=(1, 2, 0.5)); self._check(m)
        m = Mesh(); m.sphere(0, 0, 0, 5, inside=True); self._check(m)
        m = Mesh(); m.prism_roof(0, 0, 4, 2, 3, 1.5); self._check(m)
