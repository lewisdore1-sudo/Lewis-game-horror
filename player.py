"""First-person player: movement, head-bob, flashlight (Panda3D)."""
from __future__ import annotations

import math
import random

from panda3d.core import PerspectiveLens, Spotlight

from .layout import EYE_H, PLAYER_R
from .physics import move_and_collide

WALK = 2.3
SPRINT = 4.1


class Player:
    def __init__(self, app, light_root, settings):
        self.app = app
        self.x = self.y = 0.0
        self.h = self.p = 0.0
        self.vx = self.vy = 0.0
        self.stamina = 1.0
        self.bob_t = 0.0
        self.last_step_phase = 0
        self.shake = 0.0
        self.rng = random.Random()
        self.flash_on = True
        self.flicker = 1.0

        spot = Spotlight("flashlight")
        lens = PerspectiveLens()
        lens.setFov(50)
        lens.setNearFar(0.1, 40)
        spot.setLens(lens)
        spot.setExponent(18)
        spot.setAttenuation((1, 0.02, 0.022))
        self.flash_color = (1.55, 1.45, 1.25)
        spot.setColor((*self.flash_color, 1))
        if settings.get("shadows", True):
            spot.setShadowCaster(True, 1024, 1024)
        self.spot = spot
        self.flash_np = app.camera.attachNewNode(spot)
        self.flash_np.setPos(0.22, 0.05, -0.2)       # held low and to the right: long shadows
        self.flash_np.setHpr(-2.5, 3.0, 0)
        light_root.setLight(self.flash_np)

    def reset(self, x, y, h):
        self.x, self.y, self.h, self.p = x, y, h, 0.0
        self.vx = self.vy = 0.0
        self.stamina = 1.0
        self.shake = 0.0

    def toggle_flash(self):
        self.flash_on = not self.flash_on

    def look(self, dx, dy, sens, invert=False):
        self.h -= dx * sens
        self.p += (dy if invert else -dy) * sens
        self.p = max(-82.0, min(82.0, self.p))

    def move(self, dt, fwd, strafe, sprint, solid) -> float:
        """Returns horizontal speed (for footsteps)."""
        h = math.radians(self.h)
        fx, fy = -math.sin(h), math.cos(h)
        rx, ry = math.cos(h), math.sin(h)
        mx, my = fx * fwd + rx * strafe, fy * fwd + ry * strafe
        L = math.hypot(mx, my)
        running = sprint and fwd > 0 and self.stamina > 0.05
        speed = SPRINT if running else WALK
        if L > 1e-6:
            mx, my = mx / L * speed, my / L * speed
        if running and L > 0:
            self.stamina = max(0.0, self.stamina - dt / 5.5)
        else:
            self.stamina = min(1.0, self.stamina + dt / (8.0 if L > 0 else 4.0))
        k = min(1.0, dt * 10.0)
        self.vx += (mx - self.vx) * k
        self.vy += (my - self.vy) * k
        self.x, self.y = move_and_collide(self.x, self.y, self.vx * dt, self.vy * dt, PLAYER_R, solid)
        return math.hypot(self.vx, self.vy)

    def step_due(self, dt, speed) -> bool:
        """Advance head-bob; True when a foot lands."""
        if speed < 0.3:
            self.bob_t *= max(0.0, 1 - dt * 5)
            return False
        self.bob_t += dt * speed * 2.35
        phase = int(self.bob_t / math.pi)
        if phase != self.last_step_phase:
            self.last_step_phase = phase
            return True
        return False

    def apply_camera(self, cam, dt):
        bob = math.sin(self.bob_t) * 0.035
        sway = math.cos(self.bob_t * 0.5) * 0.02
        self.shake = max(0.0, self.shake - dt * 1.8)
        s = self.shake
        jh = (self.rng.random() - 0.5) * s * 6
        jp = (self.rng.random() - 0.5) * s * 6
        cam.setPos(self.x, self.y, EYE_H + bob)
        cam.setHpr(self.h + jh, self.p + jp, sway * 20 + (self.rng.random() - 0.5) * s * 4)
        v = self.flicker if self.flash_on else 0.0
        r, g, b = self.flash_color
        self.spot.setColor((r * v, g * v, b * v, 1))
