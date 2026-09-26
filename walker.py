"""The Walker's body — a tall, faceless silhouette (Panda3D)."""
from __future__ import annotations

import math
import random

from .geom import MeshSet


class WalkerVisual:
    def __init__(self, parent, mats):
        self.np = parent.attachNewNode("walker")
        self.rng = random.Random(7)
        body = MeshSet()
        b = body["black"]
        for sx in (-1, 1):
            b.cylinder(sx * 0.1, 0, 0, 0.055, 0.085, 1.08, 10)             # long thin legs
            b.sphere(sx * 0.1, -0.03, 0.03, 0.07, 8, 5, scale=(0.8, 1.6, 0.5))
        b.cylinder(0, 0, 1.02, 0.15, 0.24, 0.72, 14)                          # torso widening upward
        b.sphere(0, 0, 1.74, 0.27, 14, 8, scale=(1.15, 0.55, 0.32))           # shoulders
        b.cylinder(0, 0, 1.78, 0.045, 0.04, 0.24, 8)                          # neck
        body.build(self.np, mats, "body")

        self.arms = []
        for sx in (-1, 1):
            arm_np = self.np.attachNewNode(f"arm{sx}")
            arm_np.setPos(sx * 0.3, 0, 1.74)
            ms = MeshSet()
            ms["black"].cylinder(0, 0, -1.12, 0.03, 0.05, 1.12, 8)             # arms hang past the knees
            ms["black"].sphere(0, 0, -1.2, 0.05, 8, 6, scale=(0.7, 0.5, 2.0))  # long hands
            ms.build(arm_np, mats, "arm")
            arm_np.setR(sx * 4)
            self.arms.append((arm_np, sx))

        self.head = self.np.attachNewNode("head")
        self.head.setPos(0, 0, 2.02)
        hs = MeshSet()
        hs["black"].sphere(0, 0, 0.0, 0.13, 16, 12, scale=(0.85, 1.0, 1.45))  # no face at all
        hs.build(self.head, mats, "head")

        self.t = 0.0
        self.tilt = 0.0
        self.twitch = 0.0
        self.lunge = 0.0
        self.np.hide()

    def show(self, on: bool):
        if on:
            self.np.show()
        else:
            self.np.hide()

    def update(self, dt, brain):
        self.t += dt
        self.np.setPos(brain.x, brain.y, 0)
        self.np.setH(brain.heading)
        # when watched, the head slowly tilts, as if curious
        target_tilt = 24.0 if brain.seen else 0.0
        self.tilt += (target_tilt - self.tilt) * min(1.0, dt * (0.6 if brain.seen else 4.0))
        if brain.seen and self.rng.random() < dt * 0.35:
            self.twitch = self.rng.choice((-1, 1)) * self.rng.uniform(6, 14)
        self.twitch *= max(0.0, 1 - dt * 6)
        self.head.setR(self.tilt + self.twitch)
        self.head.setP(-6 if brain.seen else 0)
        if brain.moving:
            sw = math.sin(self.t * 5.2)
            for arm, sx in self.arms:
                arm.setP(sw * 14 * sx)
            self.np.setZ(abs(math.sin(self.t * 5.2)) * 0.03)
            self.np.setR(sw * 2.0)
        else:
            for arm, sx in self.arms:
                arm.setP(arm.getP() * max(0.0, 1 - dt * 3))
            self.np.setR(0)
