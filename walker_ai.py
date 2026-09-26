"""The Walker's brain — an original faceless entity that only moves when unseen.

Rules (from the design board):
  * VISIBILITY LOW  – dark, silent, hard to pick out.
  * BEHAVIOUR STALK – follows the player through the house.
  * RULE: MOVE WHEN UNSEEN – freezes the instant it is in view.
  * Stare at it too long and it is simply... gone. Then it turns up behind you.
  * The garden feels safe at first: it will not follow you outside until the
    house has taken two keys from you.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from . import nav
from .layout import area_at
from .physics import angle_to, line_clear, move_and_collide, point_free

FOV_HALF = 44.0          # degrees, slightly wider than the camera's half-FOV
WALKER_R = 0.28


@dataclass
class WalkerBrain:
    seed: int = 1
    x: float = 0.0
    y: float = 0.0
    active: bool = False
    seen: bool = False
    stare_time: float = 0.0
    unseen_time: float = 0.0
    last_spot: float = 99.0
    heading: float = 0.0
    moving: bool = False
    path: list[str] = field(default_factory=list)
    repath_timer: float = 0.0
    stuck_timer: float = 0.0

    def __post_init__(self):
        self.rng = random.Random(self.seed)

    # ------------------------------------------------------------------
    @staticmethod
    def speed_for(keys: int) -> float:
        return 1.35 + 0.45 * keys

    @staticmethod
    def garden_allowed(keys: int) -> bool:
        return keys >= 2

    def is_seen(self, px, py, heading, flashlight_on, sight) -> bool:
        d = math.hypot(self.x - px, self.y - py)
        view_range = 24.0 if flashlight_on else 9.0
        if d > view_range:
            return False
        margin = math.degrees(math.atan2(WALKER_R * 1.6, max(d, 0.1)))
        if angle_to(px, py, heading, self.x, self.y) > FOV_HALF + margin:
            return False
        return line_clear(px, py, self.x, self.y, sight)

    # ------------------------------------------------------------------
    def spawn_away(self, px, py, heading, sight, garden_allowed, min_d=14.0, max_d=40.0,
                   prefer_behind=False) -> bool:
        """Relocate to a node the player can't see. Returns True on success."""
        cands = []
        for name, (nx, ny) in nav.NODES.items():
            if not nav.allowed(name, garden_allowed):
                continue
            d = math.hypot(nx - px, ny - py)
            if not (min_d <= d <= max_d):
                continue
            visible = angle_to(px, py, heading, nx, ny) <= FOV_HALF + 8 and line_clear(px, py, nx, ny, sight)
            if visible:
                continue
            score = d
            if prefer_behind:
                score = abs(d - (min_d + max_d) / 2) - angle_to(px, py, heading, nx, ny) / 30.0
            cands.append((score, name))
        if not cands:
            return False
        cands.sort()
        pick = cands[0][1] if prefer_behind else self.rng.choice(cands[-max(1, len(cands) // 2):])[1]
        self.x, self.y = nav.NODES[pick]
        self.path = []
        return True

    def _goal_point(self, px, py, garden_allowed):
        """Where the Walker is heading if it can't go straight for the player."""
        if not garden_allowed and area_at(px, py) in nav.GARDEN_AREAS:
            return nav.NODES["H_N"]   # lurk at the garden door, watching
        return px, py

    # ------------------------------------------------------------------
    def update(self, dt, px, py, heading, flashlight_on, keys, solid, sight) -> list[str]:
        events: list[str] = []
        if not self.active:
            return events
        self.last_spot += dt
        garden_ok = self.garden_allowed(keys)
        seen_now = self.is_seen(px, py, heading, flashlight_on, sight)
        dist = math.hypot(self.x - px, self.y - py)

        if seen_now and not self.seen and dist < 11 and self.last_spot > 7.0:
            events.append("spotted")
            self.last_spot = 0.0
        self.seen = seen_now
        self.moving = False

        # face the player at all times — it is always watching
        self.heading = math.degrees(math.atan2(-(px - self.x), py - self.y))

        if seen_now:
            self.stare_time += dt
            self.unseen_time = 0.0
            if self.stare_time > 5.0 and dist > 3.0:
                if self.spawn_away(px, py, heading, sight, garden_ok, min_d=16.0):
                    events.append("vanished")
                self.stare_time = 0.0
            return events

        # ------------------------- unseen: it moves ----------------------
        self.stare_time = 0.0
        self.unseen_time += dt
        if dist < 0.9:
            events.append("caught")
            return events

        if self.unseen_time > 10.0 and dist > 16.0:
            if self.spawn_away(px, py, heading, sight, garden_ok, min_d=7.0, max_d=12.0, prefer_behind=True):
                events.append("teleported")
                self.unseen_time = 0.0
                return events

        gx, gy = self._goal_point(px, py, garden_ok)
        target = None
        # movement clearance: grow obstacles by the body radius so routes don't clip corners
        grown = [r.expanded(WALKER_R * 0.9) for r in solid]
        walk_clear = lambda ax, ay, bx, by: line_clear(ax, ay, bx, by, grown)
        player_blocked_area = (not garden_ok) and area_at(px, py) in nav.GARDEN_AREAS
        if not player_blocked_area and dist < 16 and walk_clear(self.x, self.y, px, py):
            target = (px, py)
            self.path = []
        else:
            self.repath_timer -= dt
            if not self.path or self.repath_timer <= 0:
                goal = nav.nearest_node(gx, gy, garden_ok, walk_clear) or nav.nearest_node(gx, gy, garden_ok)
                self.path = nav.plan(self.x, self.y, goal, garden_ok, walk_clear) if goal else []
                if not self.path and goal:
                    self.path = nav.plan(self.x, self.y, goal, garden_ok, lambda *a: True)
                self.repath_timer = 0.8
            # drop nodes we've reached or can skip past
            while self.path:
                nx, ny = nav.NODES[self.path[0]]
                if math.hypot(nx - self.x, ny - self.y) < 0.45:
                    self.path.pop(0)
                    continue
                if len(self.path) > 1:
                    n2x, n2y = nav.NODES[self.path[1]]
                    if walk_clear(self.x, self.y, n2x, n2y) and \
                            math.hypot(nx - self.x, ny - self.y) < 1.2:
                        self.path.pop(0)
                        continue
                break
            if self.path:
                target = nav.NODES[self.path[0]]
            elif math.hypot(gx - self.x, gy - self.y) > 0.5:
                target = (gx, gy)

        if target is None:
            return events

        tx, ty = target
        vx, vy = tx - self.x, ty - self.y
        d = math.hypot(vx, vy)
        if d < 1e-4:
            return events
        step = min(d, self.speed_for(keys) * dt)
        ox, oy = self.x, self.y
        nx, ny = move_and_collide(self.x, self.y, vx / d * step, vy / d * step, WALKER_R, solid)
        if not garden_ok and area_at(nx, ny) in nav.GARDEN_AREAS:
            return events          # stops at the threshold
        self.x, self.y = nx, ny
        self.moving = True
        progress = math.hypot(self.x - ox, self.y - oy)
        if progress < step * 0.25:
            self.stuck_timer += dt
            if self.stuck_timer > 1.2:
                self.path = []
                self.repath_timer = 0
                self.stuck_timer = 0
                # still wedged (a room shifted around it): slip back to a node
                if not point_free(self.x, self.y, WALKER_R, solid):
                    n = nav.nearest_node(self.x, self.y, garden_ok)
                    if n:
                        self.x, self.y = nav.NODES[n]
        else:
            self.stuck_timer = 0
        return events
