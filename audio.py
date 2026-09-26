"""Sound: ambient loops, one-shots and the Walker's 3D breathing (Panda3D)."""
from __future__ import annotations

import os
import random

from direct.showbase.Audio3DManager import Audio3DManager
from panda3d.core import AudioSound, Filename

LOOPS = ("hum_loop", "wind_loop", "drone_loop", "heartbeat_loop", "tick_loop")
ONESHOTS = ("sting", "caught", "key", "shift", "creak", "locked", "water", "paper", "door_open", "click")


class Audio:
    def __init__(self, app, asset_dir, walker_np, volume=1.0):
        self.app = app
        self.dir = asset_dir
        self.master = volume
        self.rng = random.Random()
        self.loops = {}
        self.targets = {}
        self.current = {}
        for name in LOOPS:
            s = self._load(name)
            if s:
                s.setLoop(True)
                s.setVolume(0.0)
                s.play()
                self.loops[name] = s
                self.targets[name] = 0.0
                self.current[name] = 0.0
        self.sfx = {n: self._load(n) for n in ONESHOTS}
        self.steps = {kind: [self._load(f"step_{kind}_{i}") for i in range(3)] for kind in ("wood", "stone", "grass")}

        self.a3d = None
        self.breath = None
        try:
            self.a3d = Audio3DManager(app.sfxManagerList[0], app.camera)
            self.a3d.setDopplerFactor(0.0)
            self.a3d.setDropOffFactor(1.4)
            self.breath = self.a3d.loadSfx(Filename.fromOsSpecific(os.path.join(asset_dir, "breath_loop.wav")))
            self.a3d.attachSoundToObject(self.breath, walker_np)
            self.a3d.setSoundMinDistance(self.breath, 1.5)
            self.breath.setLoop(True)
            self.breath.setVolume(0.0)
            self.breath.play()
            self.creak3d = self.a3d.loadSfx(Filename.fromOsSpecific(os.path.join(asset_dir, "creak.wav")))
            self.a3d.attachSoundToObject(self.creak3d, walker_np)
            self.a3d.setSoundMinDistance(self.creak3d, 2.0)
        except Exception as exc:          # audio is never allowed to crash the game
            print("3D audio unavailable:", exc)
            self.a3d = None

    def _load(self, name):
        path = os.path.join(self.dir, name + ".wav")
        try:
            return self.app.loader.loadSfx(Filename.fromOsSpecific(path))
        except Exception as exc:
            print("Could not load sound", name, exc)
            return None

    def set_loop(self, name, vol):
        if name in self.targets:
            self.targets[name] = vol

    def play(self, name, vol=1.0, rate=1.0):
        s = self.sfx.get(name)
        if s is None:
            return
        s.setVolume(vol * self.master)
        s.setPlayRate(rate)
        s.play()

    def step(self, surface, vol=0.5):
        s = self.rng.choice(self.steps.get(surface) or self.steps["wood"])
        if s:
            s.setVolume(vol * self.master)
            s.setPlayRate(self.rng.uniform(0.9, 1.1))
            s.play()

    def walker_sounds(self, moving: bool, active: bool, dist: float):
        if not self.breath:
            return
        target = 0.0
        if active:
            target = 0.9 if dist < 9 else 0.35
        self.breath.setVolume(target * self.master)

    def walker_creak(self):
        if self.a3d and self.creak3d.status() != AudioSound.PLAYING:
            self.creak3d.setVolume(0.9 * self.master)
            self.creak3d.play()

    def update(self, dt):
        for name, s in self.loops.items():
            cur = self.current[name]
            tgt = self.targets[name]
            cur += (tgt - cur) * min(1.0, dt * 1.5)
            self.current[name] = cur
            s.setVolume(cur * self.master)

    def silence(self):
        for name in self.targets:
            self.targets[name] = 0.0
        if self.breath:
            self.breath.setVolume(0.0)
