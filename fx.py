"""Screen effects: bloom, fog, vignette, film grain, flashes (Panda3D)."""
from __future__ import annotations

import random

from direct.gui.OnscreenImage import OnscreenImage
from panda3d.core import Fog, SamplerState, TextureStage, TransparencyAttrib

INDOOR_FOG = ((0.010, 0.010, 0.013), 0.05)
GARDEN_FOG = [((0.05, 0.06, 0.07), 0.012), ((0.05, 0.055, 0.06), 0.022),
              ((0.045, 0.045, 0.05), 0.038), ((0.04, 0.035, 0.04), 0.06)]


class FX:
    def __init__(self, app, mats, settings):
        self.app = app
        self.rng = random.Random()
        self.filters = None
        if settings.get("bloom", True):
            try:
                from direct.filter.CommonFilters import CommonFilters
                self.filters = CommonFilters(app.win, app.cam)
                ok = self.filters.setBloom(blend=(0.3, 0.4, 0.3, 0.0), mintrigger=0.6, maxtrigger=1.0,
                                           desat=0.35, intensity=1.1, size="medium")
                if not ok:
                    print("Bloom not supported on this GPU; continuing without it.")
                    self.filters = None
            except Exception as exc:
                print("Bloom disabled:", exc)
                self.filters = None

        self.fog = Fog("scene_fog")
        self.fog_col = list(INDOOR_FOG[0])
        self.fog_den = INDOOR_FOG[1]
        self.fog.setColor(*self.fog_col)
        self.fog.setExpDensity(self.fog_den)
        app.render.setFog(self.fog)

        def overlay(tex, sort):
            img = OnscreenImage(image=tex, parent=app.render2d, scale=(1, 1, 1), sort=sort)
            img.setTransparency(TransparencyAttrib.MAlpha)
            img.setBin("fixed", sort)
            img.setDepthTest(False)
            img.setDepthWrite(False)
            return img

        self.vignette = overlay(mats.clamp_tex("vignette"), 5)
        self.grain_tex = [mats.tex(f"grain_{i}") for i in range(4)]
        for t in self.grain_tex:
            t.setMinfilter(SamplerState.FT_nearest)
            t.setMagfilter(SamplerState.FT_nearest)
        self.grain = overlay(self.grain_tex[0], 6)
        self.grain.setTexScale(TextureStage.getDefault(), 7, 4)
        self.grain_on = settings.get("film_grain", True)
        if not self.grain_on:
            self.grain.hide()
        self.scan = overlay(mats.tex("scanlines"), 7)
        self.scan.setTexScale(TextureStage.getDefault(), 1, app.win.getYSize() / 256.0 / 1.5)
        if not settings.get("scanlines", False):
            self.scan.hide()
        # red / white flash layers (a full-screen image tinted by colour scale)
        self.flash = overlay(mats.clamp_tex("glow"), 8)
        self.flash.setTextureOff(1)
        self.flash.setColor(0.55, 0.0, 0.0, 1)
        self.flash.setAlphaScale(0.0)
        self.flash_amt = 0.0
        self.grain_t = 0.0
        self.grain_i = 0

    def red_flash(self, amount=0.5):
        self.flash.setColor(0.55, 0.0, 0.0, 1)
        self.flash_amt = max(self.flash_amt, amount)

    def update(self, dt, dread: float, outdoors: bool, garden_stage: int):
        col, den = GARDEN_FOG[garden_stage] if outdoors else INDOOR_FOG
        k = min(1.0, dt * 1.2)
        self.fog_col = [c + (t - c) * k for c, t in zip(self.fog_col, col)]
        self.fog_den += (den - self.fog_den) * k
        self.fog.setColor(*self.fog_col)
        self.fog.setExpDensity(self.fog_den + dread * 0.02)

        self.vignette.setAlphaScale(min(1.0, 0.78 + dread * 0.3))
        if self.grain_on:
            self.grain_t += dt
            if self.grain_t > 1 / 24:
                self.grain_t = 0.0
                self.grain_i = (self.grain_i + 1) % 4
                self.grain.setTexture(self.grain_tex[self.grain_i], 1)
                self.grain.setTexOffset(TextureStage.getDefault(), self.rng.random(), self.rng.random())
            self.grain.setAlphaScale(0.7 + dread * 1.4)
        self.flash_amt = max(0.0, self.flash_amt - dt * 1.4)
        self.flash.setAlphaScale(self.flash_amt)
